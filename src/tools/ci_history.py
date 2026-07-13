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
Data in:   the fixed fixture ``sample_data/mock_ci_history.json``, OR a per-run uploaded
    CI-history file when ``path`` is supplied (benchmarking).
Data out:  per-test stats ``{runs, fails, avg_seconds}`` (or None), or the full map.
"""

import json
from pathlib import Path

_CI_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "mock_ci_history.json"


def _load(path: str | None = None) -> dict:
    """
    Purpose:  read and filter a CI-history JSON into a test_id -> stats map.
    Inputs:   ``path`` — three-state per-run source selector:
                * None  -> read the built-in sample fixture (demo/default, unchanged);
                * ""    -> NO source: return {} (an upload run without a CI-history file —
                           we must NOT fall back to the sample fixture, per product rule);
                * "<p>" -> read that uploaded CI-history JSON.
    Outputs:  dict {test_id: {runs, fails, avg_seconds}} (empty if the source is absent/none).
    Side effects: reads the CI-history JSON (uploaded ``path`` or the fixture) from disk.
    Called by: ``get_history``, ``all_history``.
    Calls:    ``json.loads``, ``Path.read_text``.
    """
    # WHY: "" means an upload run that supplied no CI history — return empty rather than
    # leaking the sample fixture into a real benchmark (explicit product requirement).
    if path == "":
        return {}
    # WHY: None = demo/default (sample fixture); a non-empty path = an uploaded CI-history file.
    src = Path(path) if path else _CI_FILE
    # WHY: missing source degrades to an empty map — callers downgrade flags to
    # 'needs more data' rather than crashing (Blocker #3 spirit).
    if not src.exists():
        return {}
    data = json.loads(src.read_text(encoding="utf-8"))
    # WHY: drop '_'-prefixed keys (e.g. metadata/comment entries in the JSON) so only
    # real test-id records reach callers.
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_history(test_id: str, path: str | None = None) -> dict | None:
    """
    Return run stats for one test, or None if no history exists.

    Purpose:  look up CI evidence for a single test.
    Inputs:   ``test_id``; ``path`` — optional uploaded CI-history file (else fixture).
    Outputs:  ``{runs, fails, avg_seconds}`` or ``None``.
    Side effects: reads the CI-history source (via ``_load``).
    Called by: redundancy_node.
    Calls:    ``_load``.
    """
    return _load(path).get(test_id)


def all_history(path: str | None = None) -> dict:
    """
    Return the whole history map (test_id -> stats).

    Purpose:  utility to fetch every CI record at once.
    Inputs:   ``path`` — optional uploaded CI-history file (else fixture).
    Outputs:  the full ``{test_id: stats}`` map.
    Side effects: reads the CI-history source (via ``_load``).
    Called by: utility (not on the main spine).
    Calls:    ``_load``.
    """
    return _load(path)
