"""
Gemini LLM client (Gemini 2.5 Flash) — the single place the agent talks to an LLM.

Nodes never import the SDK directly; they call `complete()` through `call_tool()` so a
provider failure degrades to the deterministic fallback instead of crashing the graph
(Safety Control #5). Offline (no GEMINI_API_KEY / SDK not installed) `llm_available()`
is False and nodes take their deterministic path — the graph runs end-to-end with no key.

`complete()` raises FatalError for auth/config problems (don't retry) and TransientError
for everything else (call_tool retries with backoff, then degrades).

Architecture position: single Gemini client — the one and only place the agent talks
    to an LLM. Nodes reach it indirectly, wrapped by call_tool, so a failure degrades.
Called by: scoring_node / gap_generation_node (via call_tool wrapping complete, and
    via load_prompt / extract_json) and api.py (llm_available). Imports config for
    keys/models and the error taxonomy from tools/tool_wrapper.
Data in: a prompt string (+ optional model/system), prompt-template files under
    prompts/, and raw model response text; config's GEMINI_API_KEY / OFFLINE_MODE.
Data out: completion text, a prompt template string, parsed JSON (or None); raises
    FatalError / TransientError to steer call_tool's retry-vs-degrade behaviour.
"""

import json
import re
import time
import threading
from functools import lru_cache
from pathlib import Path

from src.config import (
    GEMINI_API_KEY, OFFLINE_MODE, REASONING_MODEL, DEFAULT_PROVIDER,
    OPENAI_API_KEY, OPENAI_MODEL, GROQ_API_KEY, GROQ_MODEL,
)
from src.observability import get_logger
from src.tools.tool_wrapper import FatalError, TransientError

_log = get_logger("llm")
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Providers treated as "Gemini" (the default). Empty string == request omitted provider.
_GEMINI_ALIASES = {"", "gemini", "google", "google-gemini"}


def _norm_provider(provider: str | None) -> str:
    """Normalise a provider name; None/blank -> DEFAULT_PROVIDER (env, default gemini)."""
    return (provider or DEFAULT_PROVIDER or "gemini").strip().lower()


# --- Per-run token-usage buffer (thread-local) -------------------------------
# complete() appends one record per successful LLM call; the calling node drains it
# right after (same thread/stack) into state["llm_usage"], which accumulates like
# audit_log. Thread-local so concurrent runs in uvicorn's threadpool never mix.
_usage = threading.local()


def _usage_buf() -> list[dict]:
    if not hasattr(_usage, "records"):
        _usage.records = []
    return _usage.records


def _record_usage(provider: str, model: str, inp, out, latency_ms: int) -> None:
    _usage_buf().append({
        "provider": provider, "model": model,
        "input_tokens": inp, "output_tokens": out, "latency_ms": latency_ms,
    })


def drain_usage() -> list[dict]:
    """Return and clear the usage records accumulated on this thread since the last drain.

    Called by scoring_node / gap_generation_node after their LLM calls so the records
    become part of the node's returned state update. Returns [] when no LLM call ran.
    """
    records = _usage_buf()
    _usage.records = []
    return records


def _classify_provider_error(e: Exception, provider: str) -> None:
    """Raise FatalError for auth/config signatures (no retry), else TransientError.

    Mirrors the original Gemini classification so call_tool retries transient failures
    and degrades to the deterministic fallback on permanent ones.
    """
    msg = str(e).lower()
    if any(k in msg for k in ("api key", "api_key", "permission", "unauthor",
                              "invalid_argument", "not found", "401", "403", "404")):
        raise FatalError(f"{provider} auth/config error: {e}")
    raise TransientError(f"{provider} call failed: {e}")


def llm_available(provider: str | None = None) -> bool:
    """True only when the chosen provider's key is configured, not offline, and SDK imports.

    Purpose: gate whether nodes take the LLM path or the deterministic fallback, for the
        provider a run selected (defaults to the env default provider when omitted).
    Inputs: optional provider name; config's OFFLINE_MODE and the provider's key; SDK import.
    Outputs: bool — True iff not offline, the provider's key is set, and its SDK is installed.
    Side effects: none (a probe import only).
    Called by: scoring_node, gap_generation_node, api.py (warm-up, no arg = default provider).
    Calls: imports the provider SDK as an availability probe.
    """
    if OFFLINE_MODE:
        return False
    prov = _norm_provider(provider)
    try:
        if prov in _GEMINI_ALIASES:
            if not GEMINI_API_KEY:
                return False
            from google import genai  # noqa: F401
            return True
        if prov == "openai":
            if not OPENAI_API_KEY:
                return False
            import openai  # noqa: F401
            return True
        if prov == "groq":
            if not GROQ_API_KEY:
                return False
            import groq  # noqa: F401
            return True
        return False  # unknown provider -> deterministic fallback
    except Exception:  # noqa: BLE001 — SDK not installed
        return False


# WHY: lru_cache(maxsize=1) makes each a lazy singleton — the SDK client is built once on
# first use and reused, avoiding repeated client construction across many LLM calls.
@lru_cache(maxsize=1)
def _gemini_client():
    """Lazily create + cache the Gemini SDK client (from GEMINI_API_KEY)."""
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


@lru_cache(maxsize=1)
def _openai_client():
    """Lazily create + cache the OpenAI SDK client (from OPENAI_API_KEY)."""
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def _groq_client():
    """Lazily create + cache the Groq SDK client (from GROQ_API_KEY)."""
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/<name>.md (raises FatalError if missing).

    Purpose: read a named LLM prompt template off disk.
    Inputs: name (stem of a file under prompts/, without the .md extension).
    Outputs: the template file's text.
    Side effects: reads a file; raises FatalError if it can't be read.
    Called by: _llm_scorecard, _llm_draft_test.
    Calls: pathlib Path.read_text.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise FatalError(f"prompt template not found: {path} ({e})")


def complete(prompt: str, *, provider: str | None = None, model: str | None = None,
             system: str | None = None) -> str:
    """Single-shot completion against the chosen provider. Raises Transient/FatalError.

    Purpose: run one prompt through the requested provider (Gemini / OpenAI / Groq) and
        return the response text, recording token usage for the run.
    Inputs: prompt text; optional provider (None -> env default), model override
        (None -> that provider's default model) and system instruction.
    Outputs: the model's response text (empty string if the response has no text).
    Side effects: one network call; appends a usage record (see drain_usage); logs debug.
    Called by: _llm_scorecard, _llm_draft_test (each wrapped by call_tool).
    Calls: the per-provider helper; raises FatalError / TransientError for call_tool.
    """
    prov = _norm_provider(provider)
    if prov in _GEMINI_ALIASES:
        return _complete_gemini(prompt, model, system)
    if prov == "openai":
        return _complete_openai(prompt, model, system)
    if prov == "groq":
        return _complete_groq(prompt, model, system)
    # Unknown provider: treat as a config error so call_tool degrades to deterministic.
    raise FatalError(f"unsupported provider: {prov}")


def _complete_gemini(prompt: str, model: str | None, system: str | None) -> str:
    if not GEMINI_API_KEY:
        raise FatalError("GEMINI_API_KEY not set")
    try:
        from google.genai import types
    except Exception as e:  # noqa: BLE001 — SDK missing
        raise FatalError(f"google-genai not installed: {e}")

    mdl = model or REASONING_MODEL
    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    try:
        t0 = time.perf_counter()
        resp = _gemini_client().models.generate_content(model=mdl, contents=prompt, config=cfg)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        text = resp.text or ""
        um = getattr(resp, "usage_metadata", None)
        _record_usage("gemini", mdl,
                      getattr(um, "prompt_token_count", None),
                      getattr(um, "candidates_token_count", None), latency_ms)
        _log.debug("gemini ok | model=%s chars=%d ms=%d", mdl, len(text), latency_ms)
        return text
    except (FatalError, TransientError):
        raise
    # WHY: classify so call_tool knows whether to retry. Auth/config signatures are
    # permanent -> FatalError (no retry); everything else -> TransientError (retry, then degrade).
    except Exception as e:  # noqa: BLE001 — classify provider errors
        _classify_provider_error(e, "gemini")


def _complete_openai(prompt: str, model: str | None, system: str | None) -> str:
    if not OPENAI_API_KEY:
        raise FatalError("OPENAI_API_KEY not set")
    try:
        from openai import OpenAI  # noqa: F401 — import probe
    except Exception as e:  # noqa: BLE001
        raise FatalError(f"openai SDK not installed: {e}")

    mdl = model or OPENAI_MODEL
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    try:
        t0 = time.perf_counter()
        resp = _openai_client().chat.completions.create(model=mdl, messages=messages)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        u = getattr(resp, "usage", None)
        _record_usage("openai", mdl,
                      getattr(u, "prompt_tokens", None),
                      getattr(u, "completion_tokens", None), latency_ms)
        _log.debug("openai ok | model=%s chars=%d ms=%d", mdl, len(text), latency_ms)
        return text
    except (FatalError, TransientError):
        raise
    except Exception as e:  # noqa: BLE001
        _classify_provider_error(e, "openai")


def _complete_groq(prompt: str, model: str | None, system: str | None) -> str:
    if not GROQ_API_KEY:
        raise FatalError("GROQ_API_KEY not set")
    try:
        from groq import Groq  # noqa: F401 — import probe
    except Exception as e:  # noqa: BLE001
        raise FatalError(f"groq SDK not installed: {e}")

    mdl = model or GROQ_MODEL
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    try:
        t0 = time.perf_counter()
        resp = _groq_client().chat.completions.create(model=mdl, messages=messages)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        u = getattr(resp, "usage", None)
        _record_usage("groq", mdl,
                      getattr(u, "prompt_tokens", None),
                      getattr(u, "completion_tokens", None), latency_ms)
        _log.debug("groq ok | model=%s chars=%d ms=%d", mdl, len(text), latency_ms)
        return text
    except (FatalError, TransientError):
        raise
    except Exception as e:  # noqa: BLE001
        _classify_provider_error(e, "groq")


def extract_json(text: str):
    """Pull the first JSON object/array out of a model response (handles ``` fences).

    Returns the parsed value, or None if nothing parseable is present.

    Purpose: defensively recover structured JSON from free-form LLM output.
    Inputs: raw model response text (may be empty, fenced, or have prose around JSON).
    Outputs: the parsed JSON value (dict/list/...), or None if none is parseable.
    Side effects: none (pure parsing).
    Called by: _llm_scorecard.
    Calls: re.search, str methods, json.loads.
    """
    if not text:
        return None
    # WHY: models often wrap JSON in a ```json ... ``` (or bare ```) code fence. This regex
    # captures the fence body if present; group(1) is the inner content, and re.DOTALL lets
    # `.*?` span newlines. Fall back to the whole text when there's no fence.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = (fenced.group(1) if fenced else text).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # WHY: if the candidate still isn't valid JSON (e.g. prose around it), fall back to the
    # outermost {...} or [...] span — the earliest opening brace/bracket to the last closing.
    starts = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(candidate[start:end + 1])
    except json.JSONDecodeError:
        return None
