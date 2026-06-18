"""
Observability — the agent records everything it does.

Two complementary channels, both fed from here so logging is consistent everywhere:

1. **Python logging** — human-readable lines to the console AND a rotating file at
   logs/agent.log. Configure once at process start via `configure_logging()`.
2. **Structured audit trail** — `audit(node, event, **details)` returns a dict that a
   node appends to `state['audit_log']` (append-only, see src/state.py) and ALSO emits
   to the logger. The report surfaces this trail, so every node entry, tool call, score,
   and human approval is captured and reviewable.

Usage in a node:

    from src.observability import audit, get_logger
    log = get_logger(__name__)
    ...
    return {"audit_log": [audit("intake", "parsed_suite", count=len(tests))]}
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "agent.log"
_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Set up console + rotating-file handlers once. Safe to call repeatedly."""
    global _configured
    if _configured:
        return
    _LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")

    root = logging.getLogger("test_optimiser")
    root.setLevel(level)
    root.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the configured root."""
    if not _configured:
        configure_logging()
    short = name.split(".")[-1]
    return logging.getLogger(f"test_optimiser.{short}")


def audit(node: str, event: str, level: int = logging.INFO, **details) -> dict:
    """Build one structured audit-trail entry AND log it. Append the return value
    to state['audit_log']. `details` is any JSON-serialisable context (counts, ids,
    scores, decisions)."""
    entry = {
        # Local system time (timezone-aware, e.g. +05:30) so the UI shows the wall-clock
        # time on this machine, not UTC.
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "node": node,
        "event": event,
        "details": details,
    }
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    get_logger(node).log(level, "%s | %s", event, detail_str)
    return entry
