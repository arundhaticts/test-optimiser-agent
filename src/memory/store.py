"""
Long-term, per-project store (the Phase 5 feedback loop).

Persists ACROSS runs, keyed by project, as JSON under .agent_memory/. Lets the agent
avoid re-suggesting a rejected change and keep confirmed-flaky tests protected. Separate
from run state (src/state.py), which lives only for one run.
"""

import json
from pathlib import Path

_MEM_DIR = Path(__file__).resolve().parents[2] / ".agent_memory"


def _file(project_id: str) -> Path:
    safe = (project_id or "default").replace("/", "_")
    return _MEM_DIR / f"{safe}.json"


def _load(project_id: str) -> dict:
    f = _file(project_id)
    base = {"decisions": [], "protected_tests": [], "known_flaky": []}
    if not f.exists():
        return base
    return {**base, **json.loads(f.read_text(encoding="utf-8"))}


def _save(project_id: str, data: dict) -> None:
    _MEM_DIR.mkdir(exist_ok=True)
    _file(project_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_decision(project_id: str, decision: dict) -> None:
    """Record an accepted/rejected recommendation, e.g.
    {'test_id': ..., 'action': 'remove', 'accepted': False}."""
    data = _load(project_id)
    data["decisions"].append(decision)
    _save(project_id, data)


def get_prior_decisions(project_id: str) -> list[dict]:
    return _load(project_id)["decisions"]


def record_flaky(project_id: str, test_id: str) -> None:
    """Remember a test was confirmed flaky (history for future triage). This does NOT
    protect it from removal — quarantining flaky tests is the whole point."""
    data = _load(project_id)
    if test_id not in data["known_flaky"]:
        data["known_flaky"].append(test_id)
    _save(project_id, data)


def get_known_flaky(project_id: str) -> list[str]:
    return _load(project_id)["known_flaky"]


def add_protected(project_id: str, test_id: str) -> None:
    """Explicitly pin a test so it is never auto-removed (human decision)."""
    data = _load(project_id)
    if test_id not in data["protected_tests"]:
        data["protected_tests"].append(test_id)
    _save(project_id, data)


def get_protected_tests(project_id: str) -> list[str]:
    """Tests the human explicitly pinned. Risk areas are handled separately via state."""
    return _load(project_id)["protected_tests"]
