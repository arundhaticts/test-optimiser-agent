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
from functools import lru_cache
from pathlib import Path

from src.config import GEMINI_API_KEY, OFFLINE_MODE, REASONING_MODEL
from src.observability import get_logger
from src.tools.tool_wrapper import FatalError, TransientError

_log = get_logger("llm")
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def llm_available() -> bool:
    """True only when a key is configured, not forced offline, and the SDK imports.

    Purpose: gate whether nodes take the LLM path or the deterministic fallback.
    Inputs: config's OFFLINE_MODE and GEMINI_API_KEY; importability of google.genai.
    Outputs: bool — True iff a key is set, not offline, and the SDK is installed.
    Side effects: none (a probe import only).
    Called by: scoring_node, gap_generation_node, api.py.
    Calls: imports google.genai as an availability probe.
    """
    if OFFLINE_MODE or not GEMINI_API_KEY:
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — SDK not installed
        return False


# WHY: lru_cache(maxsize=1) makes this a lazy singleton — the genai.Client is built once
# on first use and reused, avoiding repeated client construction across many LLM calls.
@lru_cache(maxsize=1)
def _client():
    """Purpose: lazily create and cache the Gemini SDK client.

    Inputs: config's GEMINI_API_KEY (captured at first call).
    Outputs: a cached genai.Client instance.
    Side effects: constructs the SDK client once (cached for the process).
    Called by: complete.
    Calls: google.genai.Client.
    """
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


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


def complete(prompt: str, *, model: str | None = None, system: str | None = None) -> str:
    """Single-shot completion against Gemini. Raises Transient/FatalError for call_tool.

    Purpose: run one prompt through Gemini and return the response text.
    Inputs: prompt text; optional model override (defaults to REASONING_MODEL) and
        optional system instruction.
    Outputs: the model's response text (empty string if the response has no text).
    Side effects: makes a network call to Gemini; logs a debug line on success.
    Called by: _llm_scorecard, _llm_draft_test (each wrapped by call_tool).
    Calls: _client, google.genai.types; raises FatalError / TransientError.
    """
    if not GEMINI_API_KEY:
        raise FatalError("GEMINI_API_KEY not set")
    try:
        from google.genai import types
    except Exception as e:  # noqa: BLE001 — SDK missing
        raise FatalError(f"google-genai not installed: {e}")

    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    try:
        resp = _client().models.generate_content(
            model=model or REASONING_MODEL,
            contents=prompt,
            config=cfg,
        )
        text = resp.text or ""
        _log.debug("gemini ok | model=%s chars=%d", model or REASONING_MODEL, len(text))
        return text
    except (FatalError, TransientError):
        raise
    # WHY: classify provider errors so call_tool knows whether to retry. Auth/config
    # signatures (bad key, permission, invalid argument, not found, 401/403/404) are
    # permanent -> FatalError (no retry). Everything else (timeouts, 5xx, network) is
    # assumed transient -> TransientError (call_tool retries with backoff, then degrades).
    except Exception as e:  # noqa: BLE001 — classify provider errors
        msg = str(e).lower()
        if any(k in msg for k in ("api key", "api_key", "permission", "unauthor",
                                  "invalid_argument", "not found", "401", "403", "404")):
            raise FatalError(f"gemini auth/config error: {e}")
        raise TransientError(f"gemini call failed: {e}")


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
