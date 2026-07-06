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

Architecture position: logging + audit — the cross-cutting observability layer. Both
    the Python logger and the structured audit trail originate here; imported almost
    everywhere and coupled to state.py's append-only audit_log field.
Called by: main.main / api startup (configure_logging), every module (get_logger),
    and every node (audit).
Data in: a log level; logger names; per-event details passed to audit().
Data out: configured console + rotating-file handlers (logs/agent.log), namespaced
    Logger objects, and structured audit-entry dicts (also emitted to the logger).
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "agent.log"
_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Set up console + rotating-file handlers once. Safe to call repeatedly.

    Purpose: configure the "test_optimiser" logger tree exactly once per process.
    Inputs: level (root log level; defaults to INFO).
    Outputs: none.
    Side effects: creates logs/, attaches console + rotating-file handlers, flips the
        module-level _configured guard; idempotent (returns early if already set up).
    Called by: main.main, api startup, and get_logger (lazy first-use fallback).
    Calls: Path.mkdir, logging / logging.handlers APIs.
    """
    global _configured
    # WHY: idempotency guard — bail out if already configured so repeat calls don't
    # attach duplicate handlers (which would double every log line).
    if _configured:
        return
    _LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")

    # WHY: configure our own "test_optimiser" root, not the global root; propagate=False
    # keeps our lines out of any host application's logging config.
    root = logging.getLogger("test_optimiser")
    root.setLevel(level)
    root.propagate = False

    # WHY: two handlers share one formatter — console for live visibility, and a size-based
    # rotating file (2 MB x 3 backups) so logs/agent.log persists without growing unbounded.
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
    """Return a namespaced logger under the configured root.

    Purpose: hand back a logger nested under the "test_optimiser" root.
    Inputs: name (usually __name__ or a node name; only its last dotted segment is used).
    Outputs: a logging.Logger named "test_optimiser.<short>".
    Side effects: triggers configure_logging() on first use if not yet configured.
    Called by: every module, and audit() below.
    Calls: configure_logging, logging.getLogger.
    """
    if not _configured:
        configure_logging()
    # WHY: keep only the final dotted segment so loggers read "test_optimiser.intake"
    # rather than "test_optimiser.src.nodes.intake" — shorter, consistent names in output.
    short = name.split(".")[-1]
    return logging.getLogger(f"test_optimiser.{short}")


def audit(node: str, event: str, level: int = logging.INFO, **details) -> dict:
    """Build one structured audit-trail entry AND log it. Append the return value
    to state['audit_log']. `details` is any JSON-serialisable context (counts, ids,
    scores, decisions).

    Purpose: produce one audit entry for state['audit_log'] while also logging it.
    Inputs: node (source node name), event (what happened), level (log level), and
        arbitrary JSON-serialisable **details (counts, ids, scores, decisions).
    Outputs: a dict {ts, node, event, details} for the caller to append to audit_log.
    Side effects: emits one line to the node's logger at `level`.
    Called by: every node (and the HITL nodes) as part of their return dict.
    Calls: datetime.now().astimezone().isoformat, get_logger().log.
    """
    # WHY: build the structured entry — a timestamp plus the node/event/details. This dict is
    # what the node returns under "audit_log" and the append-only reducer accumulates.
    entry = {
        # Local system time (timezone-aware, e.g. +05:30) so the UI shows the wall-clock
        # time on this machine, not UTC.
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "node": node,
        "event": event,
        "details": details,
    }
    # WHY: also emit a human-readable log line (flattening details to "k=v k=v"), so the same
    # event lands in both channels — the structured trail and the console/file log.
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    get_logger(node).log(level, "%s | %s", event, detail_str)
    return entry
