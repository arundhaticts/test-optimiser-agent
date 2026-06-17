"""
The 3 human-in-the-loop checkpoints (the red diamonds in the spec diagram).

Each HITL node builds an evidence-rich payload, pauses the graph with interrupt(), and
writes the human's decision back to state:
  1) removal/quarantine candidates  -> approved_removals
  2) priority ranking & tiers        -> approved_priority
  3) generated tests                 -> approved_generated_tests

Risk-area and memory-protected tests are pinned: they're shown but never in the default
recommendation. Quarantine is reversible; outright removal is always gated here.

run_mode:
  - interactive: interrupt() blocks; the resume value is the human's decision.
  - automated (webhook/API): no human present, so we auto-approve the *recommended*
    (reversible) set and record it — the run still completes and stays reversible.
"""

from langgraph.types import interrupt

from src.observability import audit
from src.memory import store as memory


def _decision(raw, default):
    """Resolve a resume value into the human's decision.

    Callers (api.py / main.py) wrap the decision as {"__hitl__": value} so LangGraph
    always receives a non-empty resume payload — otherwise a falsy approval (an empty
    list/dict, the natural "accept" gesture) is dropped and the interrupt re-fires.
    A None decision means "accept the recommended default".
    """
    if isinstance(raw, dict) and "__hitl__" in raw:
        raw = raw["__hitl__"]
    return raw if raw is not None else default


def is_protected(test_id: str, state) -> bool:
    """Risk-area or memory-protected tests must never be auto-removed."""
    risk = [r.lower() for r in state.get("risk_areas", [])]
    if any(r in test_id.lower() for r in risk):
        return True
    return test_id in memory.get_protected_tests(state.get("project_id"))


# ---------------------------------------------------------------- payload builders
def build_removal_payload(state) -> dict:
    """Removal/quarantine candidates with evidence; recommended excludes pinned tests."""
    candidates = []
    for f in state.get("flakiness_flags", []):
        candidates.append({"test_id": f["test_id"], "reason": "flaky",
                           "evidence": f["evidence"], "kind": "quarantine",
                           "pinned": is_protected(f["test_id"], state)})
    for f in state.get("redundancy_flags", []):
        for tid in f.get("redundant", []):
            candidates.append({"test_id": tid, "reason": "near-duplicate",
                               "evidence": f["evidence"], "kind": "merge",
                               "pinned": is_protected(tid, state)})
    recommended = [c["test_id"] for c in candidates if not c["pinned"]]
    return {"checkpoint": "approve_removals", "candidates": candidates,
            "recommended": recommended,
            "note": "Quarantine is reversible; pinned (risk-area) tests are never removed."}


def build_priority_payload(state) -> dict:
    plan = state.get("prioritised_plan", {})
    return {"checkpoint": "approve_ranking", "prioritised_plan": plan,
            "projected_coverage": state.get("projected_coverage"),
            "note": "Confirm the smoke/regression/full tiering before tests are generated."}


def build_generated_tests_payload(state) -> dict:
    generated = state.get("generated_tests", [])
    dropped = [g for g in generated if g.get("dropped")]
    valid = [g for g in generated if not g.get("dropped")]
    return {"checkpoint": "approve_tests", "generated_tests": valid,
            "dropped": dropped, "recommended": [g["id"] for g in valid],
            "note": "Dropped tests could not be auto-generated — manual attention needed."}


# ---------------------------------------------------------------- HITL nodes
def hitl_removals_node(state) -> dict:
    payload = build_removal_payload(state)
    if state.get("run_mode") == "automated":
        approved = payload["recommended"]
    else:
        approved = _decision(interrupt(payload), payload["recommended"])
    # Never let a pinned test through, whatever was submitted.
    approved = [t for t in approved if not is_protected(t, state)]
    return {"approved_removals": approved,
            "audit_log": [audit("hitl_removals", "approved",
                                count=len(approved), mode=state.get("run_mode"))]}


def hitl_priority_node(state) -> dict:
    payload = build_priority_payload(state)
    if state.get("run_mode") == "automated":
        approved = payload["prioritised_plan"]
    else:
        approved = _decision(interrupt(payload), payload["prioritised_plan"])
    return {"approved_priority": approved,
            "audit_log": [audit("hitl_priority", "approved", mode=state.get("run_mode"))]}


def hitl_generated_node(state) -> dict:
    payload = build_generated_tests_payload(state)
    if state.get("run_mode") == "automated":
        approved = payload["generated_tests"]
    else:
        approved = _decision(interrupt(payload), payload["generated_tests"])
    # The UI may approve by id (strings); resolve those back to the test objects.
    by_id = {g["id"]: g for g in payload["generated_tests"]}
    approved = [by_id.get(a, a) if isinstance(a, str) else a for a in approved]
    approved = [a for a in approved if isinstance(a, dict)]
    return {"approved_generated_tests": approved,
            "audit_log": [audit("hitl_generated", "approved",
                                count=len(approved), mode=state.get("run_mode"))]}
