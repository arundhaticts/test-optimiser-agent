"""
Gemini LLM client (Gemini 2.5 Flash) — the single place the agent talks to an LLM.

Nodes never import the SDK directly; they call `complete()` through `call_tool()` so a
provider failure degrades to the deterministic fallback instead of crashing the graph
(Safety Control #5). Offline (no GEMINI_API_KEY / SDK not installed) `llm_available()`
is False and nodes take their deterministic path — the graph runs end-to-end with no key.

`complete()` raises FatalError for auth/config problems (don't retry) and TransientError
for everything else (call_tool retries with backoff, then degrades).
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
    """True only when a key is configured, not forced offline, and the SDK imports."""
    if OFFLINE_MODE or not GEMINI_API_KEY:
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — SDK not installed
        return False


@lru_cache(maxsize=1)
def _client():
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def load_prompt(name: str) -> str:
    """Load a prompt template from prompts/<name>.md (raises FatalError if missing)."""
    path = _PROMPTS_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise FatalError(f"prompt template not found: {path} ({e})")


def complete(prompt: str, *, model: str | None = None, system: str | None = None) -> str:
    """Single-shot completion against Gemini. Raises Transient/FatalError for call_tool."""
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
    except Exception as e:  # noqa: BLE001 — classify provider errors
        msg = str(e).lower()
        if any(k in msg for k in ("api key", "api_key", "permission", "unauthor",
                                  "invalid_argument", "not found", "401", "403", "404")):
            raise FatalError(f"gemini auth/config error: {e}")
        raise TransientError(f"gemini call failed: {e}")


def extract_json(text: str):
    """Pull the first JSON object/array out of a model response (handles ``` fences).

    Returns the parsed value, or None if nothing parseable is present.
    """
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = (fenced.group(1) if fenced else text).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} or [...] span.
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
