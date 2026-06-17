"""
The retry/degrade wrapper — every external call goes through here (Blocker #3).

Ensures one failed dependency degrades gracefully instead of crashing the graph:
TransientError is retried with exponential backoff; FatalError is not retried;
every result is a uniform {'ok': bool, 'data'/'error'} envelope. `tool_error_entry`
builds the dict a node appends to state['tool_errors'] so the report can show it.
"""

import time

from src.config import TOOL_RETRIES, BACKOFF_BASE
from src.observability import get_logger

_log = get_logger("tool_wrapper")


class TransientError(Exception):
    """Temporary failure — safe to retry (timeout, 5xx, connection reset)."""


class FatalError(Exception):
    """Unrecoverable failure — do not retry (auth, repo unreadable, bad input)."""


def call_tool(fn, *args, retries=TOOL_RETRIES, backoff=BACKOFF_BASE, **kwargs):
    """Call `fn` defensively. Returns {'ok': True, 'data': ...} on success, else
    {'ok': False, 'error': ...}. Never raises for Transient/Fatal errors."""
    name = getattr(fn, "__name__", repr(fn))
    last_error = "unknown_error"
    for attempt in range(retries):
        try:
            result = fn(*args, **kwargs)
            _log.debug("tool ok | fn=%s attempt=%d", name, attempt)
            return {"ok": True, "data": result}
        except FatalError as e:
            _log.error("tool FATAL | fn=%s error=%s", name, e)
            return {"ok": False, "error": str(e), "fatal": True}
        except TransientError as e:
            last_error = str(e)
            _log.warning("tool transient | fn=%s attempt=%d error=%s", name, attempt, e)
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
        except Exception as e:  # noqa: BLE001 — unexpected; treat as transient-once
            last_error = f"{type(e).__name__}: {e}"
            _log.warning("tool error | fn=%s attempt=%d error=%s", name, attempt, last_error)
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
    _log.error("tool degraded | fn=%s error=%s", name, last_error)
    return {"ok": False, "error": last_error, "fatal": False}


def tool_error_entry(tool: str, error: str, degrade: str) -> dict:
    """Shape of an entry appended to state['tool_errors'] (surfaced in the report)."""
    return {"tool": tool, "error": error, "degrade": degrade}
