"""
Historical CI-run datastore access (mocked for the prototype).

get_history(test_id) -> {runs, fails, avg_seconds} used for flakiness and slow-test
detection. For the prototype it reads sample_data/mock_ci_history.json. Missing
history is not fatal: callers downgrade flakiness flags to 'needs more data'.
"""

import json
from pathlib import Path

_CI_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "mock_ci_history.json"


def _load() -> dict:
    if not _CI_FILE.exists():
        return {}
    data = json.loads(_CI_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_history(test_id: str) -> dict | None:
    """Return run stats for one test, or None if no history exists."""
    return _load().get(test_id)


def all_history() -> dict:
    """Return the whole history map (test_id -> stats)."""
    return _load()
