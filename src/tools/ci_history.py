"""
Historical CI-run datastore access (mocked for the prototype).

get_history(test_id) -> {runs, fails, avg_seconds} used for flakiness and slow-test
detection. For the prototype it reads sample_data/mock_ci_history.json. Missing
history is not fatal: callers downgrade flakiness flags to 'needs more data'.

Architecture position:
    Integration layer (tools/). The redundancy analysis reads it directly for
    flaky/slow evidence; a missing fixture degrades to an empty map (never fatal).
Called by:
    ``get_history`` <- redundancy_node; ``all_history`` is a utility.
Data in:   the fixed fixture ``sample_data/mock_ci_history.json``.
Data out:  per-test stats ``{runs, fails, avg_seconds}`` (or None), or the full map.
"""

import json
from pathlib import Path

_CI_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "mock_ci_history.json"


def _load() -> dict:
    """
    Purpose:  read and filter the mocked CI-history fixture into a test_id -> stats map.
    Inputs:   None (reads the fixed ``_CI_FILE`` path).
    Outputs:  dict {test_id: {runs, fails, avg_seconds}} (empty if the fixture is absent).
    Side effects: reads ``sample_data/mock_ci_history.json`` from disk.
    Called by: ``get_history``, ``all_history``.
    Calls:    ``json.loads``, ``Path.read_text``.
    """
    # WHY: missing fixture degrades to an empty map — callers downgrade flags to
    # 'needs more data' rather than crashing (Blocker #3 spirit).
    if not _CI_FILE.exists():
        return {}
    data = json.loads(_CI_FILE.read_text(encoding="utf-8"))
    # WHY: drop '_'-prefixed keys (e.g. metadata/comment entries in the JSON) so only
    # real test-id records reach callers.
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_history(test_id: str) -> dict | None:
    """
    Return run stats for one test, or None if no history exists.

    Purpose:  look up CI evidence for a single test.
    Inputs:   ``test_id``.
    Outputs:  ``{runs, fails, avg_seconds}`` or ``None``.
    Side effects: reads the fixture (via ``_load``).
    Called by: redundancy_node.
    Calls:    ``_load``.
    """
    return _load().get(test_id)


def all_history() -> dict:
    """
    Return the whole history map (test_id -> stats).

    Purpose:  utility to fetch every CI record at once.
    Inputs:   None.
    Outputs:  the full ``{test_id: stats}`` map.
    Side effects: reads the fixture (via ``_load``).
    Called by: utility (not on the main spine).
    Calls:    ``_load``.
    """
    return _load()
