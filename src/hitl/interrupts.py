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

Architecture position:
    hitl/ = the 3 human approval interrupts and the agent's safety boundary.
    is_protected is the pin-enforcement primitive reused wherever removals are
    decided; the 3 nodes are the only places destructive intent becomes approved.

Called by:
    src/graph.py wires the 3 HITL nodes; prioritisation._tier_for and revise_node
    call is_protected to keep pinned tests off removal/downgrade paths.

Data in:  run state (flags, prioritised_plan, generated_tests, run_mode, risk_areas).
Data out: approved_removals / approved_priority / approved_generated_tests.

Side effects: interrupt() pauses the graph (interactive mode); every node appends
    to audit_log.
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

    Purpose:      unwrap the {"__hitl__": ...} resume envelope into a plain decision.
    Inputs:       raw resume value and the default to use when the decision is None.
    Outputs:      the human's decision, or the default.
    Side effects: None (pure).
    Called by:    the 3 HITL nodes.
    Calls:        (dict/isinstance checks only).
    """
    # WHY: peel the envelope. The envelope exists precisely so a falsy-but-real
    # approval (e.g. []) still resumes — only genuine None means "use the default".
    if isinstance(raw, dict) and "__hitl__" in raw:
        raw = raw["__hitl__"]
    return raw if raw is not None else default


def is_protected(test_id: str, state) -> bool:
    """Risk-area or memory-protected tests must never be auto-removed.

    Purpose:      pin-enforcement predicate reused everywhere removals are decided.
    Inputs:       test_id and run state (risk_areas, project_id).
    Outputs:      True if the test is pinned (risk-area OR memory-protected).
    Side effects: reads memory (get_protected_tests); no writes.
    Called by:    hitl_removals_node, build_removal_payload, prioritisation._tier_for,
                  revise_node.
    Calls:        memory.get_protected_tests.
    """
    risk = [r.lower() for r in state.get("risk_areas", [])]
    # WHY: risk-area match is a case-insensitive substring of the test id (e.g.
    # risk "payment" pins "test_payment_refund").
    if any(r in test_id.lower() for r in risk):
        return True
    # WHY: second pin source — tests the human explicitly pinned in durable memory.
    return test_id in memory.get_protected_tests(state.get("project_id"))


# ---------------------------------------------------------------- payload builders
def build_removal_payload(state) -> dict:
    """Removal/quarantine candidates with evidence; recommended excludes pinned tests.

    Purpose:      build the HITL-1 payload (candidates + safe recommendation).
    Inputs:       run state (flakiness_flags, redundancy_flags, ...).
    Outputs:      payload dict for interrupt() / automated approval.
    Side effects: reads memory via is_protected; no writes.
    Called by:    hitl_removals_node.
    Calls:        is_protected.
    """
    candidates = []
    # WHY: flaky tests are quarantine candidates (reversible), tagged with evidence.
    for f in state.get("flakiness_flags", []):
        candidates.append({"test_id": f["test_id"], "reason": "flaky",
                           "evidence": f["evidence"], "kind": "quarantine",
                           "pinned": is_protected(f["test_id"], state)})
    # WHY: each redundancy cluster contributes its redundant members as merge candidates.
    for f in state.get("redundancy_flags", []):
        for tid in f.get("redundant", []):
            candidates.append({"test_id": tid, "reason": "near-duplicate",
                               "evidence": f["evidence"], "kind": "merge",
                               "pinned": is_protected(tid, state)})
    # WHY: the DEFAULT recommendation never includes pinned tests — pins are shown but
    # excluded from the auto/one-click accept set.
    recommended = [c["test_id"] for c in candidates if not c["pinned"]]
    return {"checkpoint": "approve_removals", "candidates": candidates,
            "recommended": recommended,
            "note": "Quarantine is reversible; pinned (risk-area) tests are never removed."}


def build_priority_payload(state) -> dict:
    """Build the HITL-2 payload (proposed tiering + projected coverage).

    Purpose:      present the smoke/regression/full ranking for sign-off.
    Inputs:       run state (prioritised_plan, projected_coverage).
    Outputs:      payload dict for interrupt() / automated approval.
    Side effects: None (pure).
    Called by:    hitl_priority_node.
    Calls:        (state access only).
    """
    plan = state.get("prioritised_plan", {})
    return {"checkpoint": "approve_ranking", "prioritised_plan": plan,
            "projected_coverage": state.get("projected_coverage"),
            "note": "Confirm the smoke/regression/full tiering before tests are generated."}


def build_generated_tests_payload(state) -> dict:
    """Build the HITL-3 payload (valid drafts vs dropped drafts).

    Purpose:      present generated gap tests for acceptance into the plan.
    Inputs:       run state (generated_tests).
    Outputs:      payload dict for interrupt() / automated approval.
    Side effects: None (pure).
    Called by:    hitl_generated_node.
    Calls:        (state access only).
    """
    generated = state.get("generated_tests", [])
    # WHY: split drafts — dropped ones (failed sandbox/generation) are surfaced
    # separately for manual attention; only valid ones are recommended.
    dropped = [g for g in generated if g.get("dropped")]
    valid = [g for g in generated if not g.get("dropped")]
    return {"checkpoint": "approve_tests", "generated_tests": valid,
            "dropped": dropped, "recommended": [g["id"] for g in valid],
            "note": "Dropped tests could not be auto-generated — manual attention needed."}


# ---------------------------------------------------------------- HITL nodes
def hitl_removals_node(state) -> dict:
    """HITL-1: approve which flaky/duplicate tests may be quarantined/merged.

    Purpose:      turn removal candidates into an approved, pin-safe removal list.
    Inputs:       run state (flags, run_mode, risk_areas, project_id).
    Outputs:      {approved_removals, audit_log[+]}.
    Side effects: interrupt() pauses the graph (interactive); appends to audit_log.
    Called by:    src/graph.py.
    Calls:        build_removal_payload, interrupt, _decision, is_protected, audit.
    """
    payload = build_removal_payload(state)
    # WHY: automated (no human) -> accept the safe recommended set; interactive ->
    # block on interrupt() and take the human's decision (default = recommended).
    if state.get("run_mode") == "automated":
        approved = payload["recommended"]
    else:
        approved = _decision(interrupt(payload), payload["recommended"])
    # Never let a pinned test through, whatever was submitted.
    # WHY: re-filter defensively — even a human/API submission cannot remove a pinned
    # (risk-area or memory-protected) test.
    approved = [t for t in approved if not is_protected(t, state)]
    return {"approved_removals": approved,
            "audit_log": [audit("hitl_removals", "approved",
                                count=len(approved), mode=state.get("run_mode"))]}


def hitl_priority_node(state) -> dict:
    """HITL-2: approve the smoke/regression/full ranking before generation.

    Purpose:      capture the approved tiering/ranking of the surviving suite.
    Inputs:       run state (prioritised_plan, run_mode).
    Outputs:      {approved_priority, audit_log[+]}.
    Side effects: interrupt() pauses the graph (interactive); appends to audit_log.
    Called by:    src/graph.py.
    Calls:        build_priority_payload, interrupt, _decision, audit.
    """
    payload = build_priority_payload(state)
    # WHY: automated -> accept the proposed plan as-is; interactive -> block on
    # interrupt() (default = the proposed plan if the human just accepts).
    if state.get("run_mode") == "automated":
        approved = payload["prioritised_plan"]
    else:
        approved = _decision(interrupt(payload), payload["prioritised_plan"])
    return {"approved_priority": approved,
            "audit_log": [audit("hitl_priority", "approved", mode=state.get("run_mode"))]}


def hitl_generated_node(state) -> dict:
    """HITL-3: approve which generated gap tests are accepted into the plan.

    Purpose:      resolve the human's picks into concrete generated-test objects.
    Inputs:       run state (generated_tests, run_mode).
    Outputs:      {approved_generated_tests, audit_log[+]}.
    Side effects: interrupt() pauses the graph (interactive); appends to audit_log.
    Called by:    src/graph.py.
    Calls:        build_generated_tests_payload, interrupt, _decision, audit.
    """
    payload = build_generated_tests_payload(state)
    # WHY: automated -> accept all valid drafts; interactive -> block on interrupt()
    # (default = all valid drafts if the human just accepts).
    if state.get("run_mode") == "automated":
        approved = payload["generated_tests"]
    else:
        approved = _decision(interrupt(payload), payload["generated_tests"])
    # The UI may approve by id (strings); resolve those back to the test objects.
    # WHY: build an id->object map so string picks from the UI resolve to full
    # test dicts; non-string entries (already objects) pass through untouched.
    by_id = {g["id"]: g for g in payload["generated_tests"]}
    approved = [by_id.get(a, a) if isinstance(a, str) else a for a in approved]
    # WHY: keep only resolved dicts — drop any id that didn't map to a known test.
    approved = [a for a in approved if isinstance(a, dict)]
    return {"approved_generated_tests": approved,
            "audit_log": [audit("hitl_generated", "approved",
                                count=len(approved), mode=state.get("run_mode"))]}
