"""
Expected-findings (golden answer key) loader — a BENCHMARK reference, not an analysis input.

Unlike criteria / CI history (which feed the analysis), the expected-findings file is the
known-correct answer a run is graded against. ``load`` returns it so ``report`` can compare
the agent's actual findings to it and emit a ``benchmark`` result. It never influences the
analysis itself.

Architecture position:
    Integration layer (tools/). Reached via ``tool_wrapper.call_tool`` from ``report_node``.
    A missing/absent source is not fatal — it just means "no benchmark this run".
Called by:
    ``load`` <- report_node (via ``call_tool``).
Data in:   the sample golden fixture ``sample_data/expected_findings.json``, OR a per-run
    uploaded expected-findings file when ``path`` is supplied (benchmarking).
Data out:  the parsed expected-findings dict (duplicates / flaky / slow / coverage_gaps), or
    None when there is no source.
"""

import json
from pathlib import Path

_GOLDEN_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "expected_findings.json"


def load(path: str | None = None) -> dict | None:
    """
    Load the expected-findings answer key for benchmarking.

    Purpose:  supply the golden findings ``report`` grades the run against.
    Inputs:   ``path`` — three-state per-run source selector (mirrors criteria / CI history):
                * None  -> read the sample golden fixture (demo/default);
                * ""    -> NO source: return None (an upload run without expected findings —
                           we must NOT fall back to the sample golden, per product rule);
                * "<p>" -> read that uploaded expected-findings JSON.
    Outputs:  the parsed dict, or None when there is no source / it's missing.
    Side effects: reads the expected-findings JSON (uploaded ``path`` or the fixture).
    Called by: report_node (via ``call_tool``).
    Calls:    ``json.loads``, ``Path.read_text``.
    """
    # WHY: "" means an upload run that supplied no expected findings — return None so no
    # benchmark is produced (and the sample golden is NOT leaked into a real run).
    if path == "":
        return None
    # WHY: None = demo/default (sample golden); a non-empty path = an uploaded answer key.
    src = Path(path) if path else _GOLDEN_FILE
    # WHY: a missing source just means "no benchmark" — never fatal.
    if not src.exists():
        return None
    return json.loads(src.read_text(encoding="utf-8"))
