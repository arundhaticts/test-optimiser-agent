"""
Long-term, per-project store (the Phase 5 feedback loop).

Persists ACROSS runs, keyed by project, as JSON under .agent_memory/. Lets the agent
avoid re-suggesting a rejected change and keep confirmed-flaky tests protected. Separate
from run state (src/state.py), which lives only for one run.

Architecture position:
    memory/ = the durable per-project store. All persistence funnels through the
    private _file/_load/_save helpers; the public save/get/record/add functions
    are thin read-modify-write wrappers over them.

Called by:
    nodes/retrieval (get_prior_decisions), nodes/report (save_decision,
    record_flaky), and hitl/interrupts.is_protected (get_protected_tests).

Data in:  project_id plus a decision dict or a test id.
Data out: lists of decisions / protected ids / known-flaky ids.

Side effects: reads and writes JSON files under .agent_memory/.
"""

import json
from pathlib import Path

_MEM_DIR = Path(__file__).resolve().parents[2] / ".agent_memory"


def _file(project_id: str) -> Path:
    """Map a project id to its memory JSON path.

    Purpose:      resolve the per-project store file path.
    Inputs:       project_id (may be None/empty).
    Outputs:      a Path under .agent_memory/.
    Side effects: None (pure) — computes a path only.
    Called by:    _load, _save.
    Calls:        (pathlib / str ops only).
    """
    # WHY: default missing ids and slugify "/" so a project id can't escape the dir
    # or create nested paths — one flat file per project.
    safe = (project_id or "default").replace("/", "_")
    return _MEM_DIR / f"{safe}.json"


def _load(project_id: str) -> dict:
    """Load a project's memory, defaulting to a fresh, fully-keyed base.

    Purpose:      read the store, always returning the full schema.
    Inputs:       project_id.
    Outputs:      dict with decisions / protected_tests / known_flaky keys.
    Side effects: reads the JSON file if present (no write).
    Called by:    every public getter/setter below.
    Calls:        _file, json.loads.
    """
    f = _file(project_id)
    # WHY: start from a fully-keyed base so callers can index keys unconditionally.
    base = {"decisions": [], "protected_tests": [], "known_flaky": []}
    # WHY: no file yet -> a brand-new project, return the empty base.
    if not f.exists():
        return base
    # WHY: overlay stored data on the base so older files missing a key still load.
    return {**base, **json.loads(f.read_text(encoding="utf-8"))}


def _save(project_id: str, data: dict) -> None:
    """Persist a project's memory dict to disk.

    Purpose:      write the full memory dict back atomically-per-call.
    Inputs:       project_id and the complete data dict.
    Outputs:      None.
    Side effects: creates .agent_memory/ if needed and writes the JSON file.
    Called by:    save_decision, record_flaky, add_protected.
    Calls:        _file, json.dumps, Path.mkdir / write_text.
    """
    # WHY: ensure the memory dir exists before the first write of a run.
    _MEM_DIR.mkdir(exist_ok=True)
    _file(project_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_decision(project_id: str, decision: dict) -> None:
    """Record an accepted/rejected recommendation, e.g.
    {'test_id': ..., 'action': 'remove', 'accepted': False}.

    Purpose:      append one decision to the project's durable history.
    Inputs:       project_id and a decision dict.
    Outputs:      None.
    Side effects: writes the memory JSON file.
    Called by:    nodes/report.
    Calls:        _load, _save.
    """
    # WHY: read-modify-write — append the new decision, then persist.
    data = _load(project_id)
    data["decisions"].append(decision)
    _save(project_id, data)


def get_prior_decisions(project_id: str) -> list[dict]:
    """Return the project's recorded decisions.

    Purpose:      surface past accept/reject history to the retrieval node.
    Inputs:       project_id.
    Outputs:      list of decision dicts.
    Side effects: reads the memory JSON file.
    Called by:    nodes/retrieval.
    Calls:        _load.
    """
    return _load(project_id)["decisions"]


def record_flaky(project_id: str, test_id: str) -> None:
    """Remember a test was confirmed flaky (history for future triage). This does NOT
    protect it from removal — quarantining flaky tests is the whole point.

    Purpose:      persist a confirmed-flaky test id for future-run triage.
    Inputs:       project_id and test_id.
    Outputs:      None.
    Side effects: writes the memory JSON file.
    Called by:    nodes/report.
    Calls:        _load, _save.
    """
    data = _load(project_id)
    # WHY: de-dup — record each flaky id at most once.
    if test_id not in data["known_flaky"]:
        data["known_flaky"].append(test_id)
    _save(project_id, data)


def get_known_flaky(project_id: str) -> list[str]:
    """Return confirmed-flaky test ids for the project.

    Purpose:      expose known-flaky history (available to triage callers).
    Inputs:       project_id.
    Outputs:      list of test ids.
    Side effects: reads the memory JSON file.
    Called by:    (available utility).
    Calls:        _load.
    """
    return _load(project_id)["known_flaky"]


def add_protected(project_id: str, test_id: str) -> None:
    """Explicitly pin a test so it is never auto-removed (human decision).

    Purpose:      pin a test id so is_protected keeps it off removal lists.
    Inputs:       project_id and test_id.
    Outputs:      None.
    Side effects: writes the memory JSON file.
    Called by:    human-pin flows.
    Calls:        _load, _save.
    """
    data = _load(project_id)
    # WHY: de-dup — a test is pinned once regardless of repeated pins.
    if test_id not in data["protected_tests"]:
        data["protected_tests"].append(test_id)
    _save(project_id, data)


def get_protected_tests(project_id: str) -> list[str]:
    """Tests the human explicitly pinned. Risk areas are handled separately via state.

    Purpose:      list memory-protected test ids for pin enforcement.
    Inputs:       project_id.
    Outputs:      list of pinned test ids.
    Side effects: reads the memory JSON file.
    Called by:    hitl/interrupts.is_protected, nodes/retrieval.
    Calls:        _load.
    """
    return _load(project_id)["protected_tests"]
