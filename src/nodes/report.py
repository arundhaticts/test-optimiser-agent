"""
Node 10 — Render Outputs & Update Memory.

Renders the four deliverables (Test Health Scorecard, Coverage & Gap Map, Redundancy &
Flakiness Report, Optimised Plan + generated tests + context sources) into final_outputs,
surfacing tool_errors so degraded results are visible. Then closes the Phase 5 feedback
loop: records the run's decisions and newly-confirmed flaky tests to long-term memory.
"""

from src.observability import audit
from src.memory import store as memory


def report_node(state) -> dict:
    final = dict(state.get("final_outputs", {}))

    final["scorecard"] = state.get("scorecard", {})
    final["coverage_gap_map"] = {
        "coverage_map": state.get("coverage_map", {}),
        "gaps": state.get("coverage_gaps", []),
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

    # Include this node's own entry so the embedded trail is complete.
    entry = audit("report", "rendered_outputs",
                  deliverables=4, tool_errors=len(final["tool_errors"]))
    final["audit_log"] = state.get("audit_log", []) + [entry]

    # --- Phase 5 feedback loop: persist decisions + confirmed flaky tests ---
    project_id = state.get("project_id")
    approved = set(state.get("approved_removals", []))
    candidates = {f["test_id"] for f in state.get("flakiness_flags", [])}
    for f in state.get("redundancy_flags", []):
        candidates.update(f.get("redundant", []))
    for tid in candidates:
        memory.save_decision(project_id, {"test_id": tid, "action": "remove",
                                          "accepted": tid in approved})
    for f in state.get("flakiness_flags", []):
        if f["test_id"] in approved:
            memory.record_flaky(project_id, f["test_id"])

    return {"final_outputs": final, "audit_log": [entry]}
