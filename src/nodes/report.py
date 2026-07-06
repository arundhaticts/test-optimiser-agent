"""
Node 10 — Render Outputs & Update Memory.

Renders the four deliverables (Test Health Scorecard, Coverage & Gap Map, Redundancy &
Flakiness Report, Optimised Plan + generated tests + context sources) into final_outputs,
surfacing tool_errors so degraded results are visible. Then closes the Phase 5 feedback
loop: records the run's decisions and newly-confirmed flaky tests to long-term memory.

Architecture position: Node 10 of 10 — Report; the pipeline's final node, runs after
assemble, before END.
Called by: the graph (src/graph.py).
Data in: final_outputs, scorecard, approved_generated_tests, coverage_gaps,
coverage_map, projected_coverage, redundancy_flags, flakiness_flags, slow_flags,
retrieved_context, tool_errors, audit_log, project_id, approved_removals.
Data out: final_outputs (all 4 deliverables + extras), audit_log[+].
"""

from src.observability import audit
from src.memory import store as memory


def report_node(state) -> dict:
    """Render the four deliverables and persist decisions to long-term memory.

    Purpose: assemble the scorecard, coverage/gap map, redundancy/flakiness report, and
        generated tests into final_outputs; annotate gaps now addressed by approved tests;
        then save decisions and confirmed-flaky tests to memory (Phase-5 feedback loop).
    Inputs: state — reads final_outputs, scorecard, approved_generated_tests,
        coverage_gaps, coverage_map, projected_coverage, redundancy_flags,
        flakiness_flags, slow_flags, retrieved_context, tool_errors, audit_log,
        project_id, approved_removals.
    Outputs: dict with final_outputs (all deliverables) and audit_log[+].
    Side effects: memory writes (save_decision, record_flaky) to
        .agent_memory/{project_id}.json; appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: audit, memory.save_decision, memory.record_flaky.
    """
    final = dict(state.get("final_outputs", {}))

    final["scorecard"] = state.get("scorecard", {})
    # Mark gaps that an APPROVED generated test now addresses, so the coverage view
    # reflects the human's decision. The criterion stays a "gap" (the drafted test isn't
    # merged/verified yet) but is annotated with the test that addresses it.
    # WHY: keep only dict entries (approved list may hold ids), then build a
    # criterion_id -> generated_test_id map from approved tests that name a criterion.
    approved_gen = [g for g in state.get("approved_generated_tests", []) if isinstance(g, dict)]
    addressed = {g.get("criterion_id"): g.get("id") for g in approved_gen if g.get("criterion_id")}
    # WHY: annotate each gap that an approved test addresses with "addressed_by"; copy each
    # gap before mutating so source state isn't changed. The gap stays a gap (not verified).
    gaps = []
    for gp in state.get("coverage_gaps", []):
        gp = dict(gp)
        if gp.get("criterion_id") in addressed:
            gp["addressed_by"] = addressed[gp["criterion_id"]]
        gaps.append(gp)
    final["coverage_gap_map"] = {
        "coverage_map": state.get("coverage_map", {}),
        "gaps": gaps,
        "projected_coverage": state.get("projected_coverage"),
    }
    final["redundancy_flakiness_report"] = {
        "redundancy_flags": state.get("redundancy_flags", []),
        "flakiness_flags": state.get("flakiness_flags", []),
        "slow_flags": state.get("slow_flags", []),
    }
    final["generated_tests"] = state.get("approved_generated_tests", [])
    final["context_sources"] = state.get("retrieved_context", [])
    final["tool_errors"] = state.get("tool_errors", [])

    # WHY: embed the full accumulated audit trail plus this node's own entry into
    # final_outputs so the deliverable carries the complete trace.
    # Include this node's own entry so the embedded trail is complete.
    entry = audit("report", "rendered_outputs",
                  deliverables=4, tool_errors=len(final["tool_errors"]))
    final["audit_log"] = state.get("audit_log", []) + [entry]

    # WHY: persist outcomes so future runs learn — every removal candidate (flaky tests +
    # redundant cluster members) is saved with whether the human accepted it, and flaky
    # tests the human approved for removal are recorded as confirmed-flaky.
    # --- Phase 5 feedback loop: persist decisions + confirmed flaky tests ---
    project_id = state.get("project_id")
    approved = set(state.get("approved_removals", []))
    # WHY: candidate set = all flaky test ids plus every redundant-cluster member.
    candidates = {f["test_id"] for f in state.get("flakiness_flags", [])}
    for f in state.get("redundancy_flags", []):
        candidates.update(f.get("redundant", []))
    for tid in candidates:
        memory.save_decision(project_id, {"test_id": tid, "action": "remove",
                                          "accepted": tid in approved})
    # WHY: only flaky tests the human actually approved for removal become confirmed-flaky.
    for f in state.get("flakiness_flags", []):
        if f["test_id"] in approved:
            memory.record_flaky(project_id, f["test_id"])

    return {"final_outputs": final, "audit_log": [entry]}
