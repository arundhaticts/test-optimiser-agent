"""
The retry/degrade wrapper — every external call goes through here (Blocker #3).

Ensures one failed dependency degrades gracefully instead of crashing the graph:
TransientError is retried with exponential backoff; FatalError is not retried;
every result is a uniform {'ok': bool, 'data'/'error'} envelope. `tool_error_entry`
builds the dict a node appends to state['tool_errors'] so the report can show it.

Architecture position:
    The single choke point of the integration layer (Blocker #3): every external call
    the graph makes is funnelled through ``call_tool`` so no node ever touches a file,
    SDK, subprocess, or network dependency directly.

Called by:
    Every I/O node (intake, coverage, retrieval, scoring, gap_generation) and, through
    them, ``src/llm.py`` (LLM calls are wrapped by ``call_tool`` too).
Data in:  a callable ``fn`` plus its positional/keyword arguments, and the retry/backoff
          knobs (default from ``src.config`` TOOL_RETRIES / BACKOFF_BASE).
Data out: the ``{'ok': bool, 'data'/'error', 'fatal'}`` envelope, and — via
          ``tool_error_entry`` — the ``{tool, error, degrade}`` dict appended to
          state['tool_errors'].
"""

import time

from src.config import TOOL_RETRIES, BACKOFF_BASE
from src.observability import get_logger

_log = get_logger("tool_wrapper")


class TransientError(Exception):
    """
    Temporary failure — safe to retry (timeout, 5xx, connection reset).

    Purpose:  signal that ``call_tool`` should retry with backoff rather than degrade.
    Inputs:   raised with a human-readable message by tools/llm on recoverable errors.
    Outputs:  N/A (exception type).
    Side effects: None (pure).
    Called by: raised in ``src/llm.py`` and node LLM helpers on network-ish failures.
    Calls:    None.
    """


class FatalError(Exception):
    """
    Unrecoverable failure — do not retry (auth, repo unreadable, bad input).

    Purpose:  signal that ``call_tool`` must NOT retry and should return immediately with
              ``fatal: True`` so the node degrades on the very first attempt.
    Inputs:   raised with a message by tools/llm on non-recoverable errors.
    Outputs:  N/A (exception type).
    Side effects: None (pure).
    Called by: raised in ``repo_reader``, ``test_parser``, ``src/llm.py`` (auth/config).
    Calls:    None.
    """


def call_tool(fn, *args, retries=TOOL_RETRIES, backoff=BACKOFF_BASE, **kwargs):
    """
    Call `fn` defensively. Returns {'ok': True, 'data': ...} on success, else
    {'ok': False, 'error': ...}. Never raises for Transient/Fatal errors.

    Purpose:  the universal retry/degrade wrapper — the one place every external call is
              made so a failed dependency degrades instead of crashing the graph.
    Inputs:   ``fn`` and its ``*args``/``**kwargs``; ``retries`` (attempt count) and
              ``backoff`` (exponential base), defaulted from config.
    Outputs:  the envelope ``{'ok': bool, 'data'|'error', 'fatal'?}``:
                - success -> ``{'ok': True, 'data': <return value>}``
                - fatal   -> ``{'ok': False, 'error': str, 'fatal': True}`` (no retry)
                - degrade -> ``{'ok': False, 'error': str, 'fatal': False}`` (retries used)
    Side effects: logging (debug/warning/error) and ``time.sleep`` between retries.
    Called by: every I/O node (intake, coverage, retrieval, scoring, gap_generation).
    Calls:    ``fn``, ``time.sleep``, ``get_logger`` (module logger).
    """
    name = getattr(fn, "__name__", repr(fn))
    last_error = "unknown_error"
    for attempt in range(retries):
        try:
            # WHY: happy path — first successful call returns immediately, no retries.
            result = fn(*args, **kwargs)
            _log.debug("tool ok | fn=%s attempt=%d", name, attempt)
            return {"ok": True, "data": result}
        except FatalError as e:
            # WHY: fatal errors (auth, unreadable repo, bad input) can't be fixed by
            # retrying, so bail out at once with fatal=True and let the node degrade.
            _log.error("tool FATAL | fn=%s error=%s", name, e)
            return {"ok": False, "error": str(e), "fatal": True}
        except TransientError as e:
            # WHY: transient errors are recoverable — record and fall through to backoff.
            last_error = str(e)
            _log.warning("tool transient | fn=%s attempt=%d error=%s", name, attempt, e)
            if attempt < retries - 1:
                # WHY: exponential backoff — sleep grows as backoff**attempt (0-based:
                # attempt 0 -> backoff**0 = 1s, attempt 1 -> backoff**1, ...); skipped
                # on the last attempt since no further retry follows.
                time.sleep(backoff ** attempt)
        except Exception as e:  # noqa: BLE001 — unexpected; treat as transient-once
            # WHY: any other exception is unexpected but treated like a transient error
            # (retry with backoff) so an unforeseen bug still degrades, not crashes.
            last_error = f"{type(e).__name__}: {e}"
            _log.warning("tool error | fn=%s attempt=%d error=%s", name, attempt, last_error)
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
    # WHY: all retries exhausted — final degrade envelope (fatal=False) so the node
    # continues on its deterministic fallback rather than stalling the run.
    _log.error("tool degraded | fn=%s error=%s", name, last_error)
    return {"ok": False, "error": last_error, "fatal": False}


def tool_error_entry(tool: str, error: str, degrade: str) -> dict:
    """
    Shape of an entry appended to state['tool_errors'] (surfaced in the report).

    Purpose:  build the record a node appends to state['tool_errors'] describing which
              tool failed, why, and what fallback ("degrade") the node used instead.
    Inputs:   ``tool`` name, ``error`` message, ``degrade`` (fallback description).
    Outputs:  ``{'tool': ..., 'error': ..., 'degrade': ...}``.
    Side effects: None (pure).
    Called by: intake, coverage, retrieval, scoring, gap_generation nodes.
    Calls:    None.
    """
    return {"tool": tool, "error": error, "degrade": degrade}
