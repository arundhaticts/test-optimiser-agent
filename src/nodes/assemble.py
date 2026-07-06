"""
Node 9 — Assemble Optimised Plan.

Pure assembly (no external calls): combines kept tests, approved removals/merges, the
tiering, and approved generated tests into one plan shown side-by-side with the current
suite. Writes final_outputs.optimised_plan.

Architecture position: Node 9 of 10 — Assemble; runs after HITL 3 (approve tests),
before report.
Called by: the graph (src/graph.py).
Data in: normalised_suite, approved_removals, redundancy_flags, prioritised_plan,
approved_generated_tests, projected_coverage, final_outputs.
Data out: final_outputs (optimised_plan section), audit_log[+].
"""

from src.observability import audit


def assemble_node(state) -> dict:
    """Assemble the side-by-side current-vs-proposed optimised plan.

    Purpose: pure assembly — combine kept tests, approved removals/merges, tiering, and
        approved generated tests into final_outputs.optimised_plan.
    Inputs: state — reads normalised_suite, approved_removals, redundancy_flags,
        prioritised_plan, approved_generated_tests, projected_coverage, final_outputs.
    Outputs: dict with final_outputs (optimised_plan added), audit_log[+].
    Side effects: appends an audit log entry (no external calls).
    Called by: the graph (src/graph.py).
    Calls: audit.
    """
    suite = state.get("normalised_suite", [])
    removals = state.get("approved_removals", [])
    # WHY: turn each near-duplicate flag into a {keep, merge} entry for the plan view.
    merges = [{"keep": f["keep"], "merge": f["redundant"]}
              for f in state.get("redundancy_flags", [])]
    plan = state.get("prioritised_plan", {})
    generated = state.get("approved_generated_tests", [])

    # WHY: build the deliverable — "current" is the suite as-is; "proposed" is the change
    # set (removed/merged/tiers/generated) with "kept" = surviving tests after removals.
    optimised_plan = {
        "current": {"total_tests": len(suite),
                    "test_ids": [t["id"] for t in suite]},
        "proposed": {
            "removed": removals,
            "merged": merges,
            "tiers": plan.get("tiers", {}),
            "generated": [g.get("id") for g in generated],
            # WHY: kept = every suite test whose id is not in the removals set.
            "kept": [t["id"] for t in suite if t["id"] not in set(removals)],
        },
        "projected_coverage": state.get("projected_coverage"),
        "goal": plan.get("goal"),
    }

    # WHY: copy existing final_outputs before adding our section so report's later additions
    # (and last-writer-wins merge) stay intact.
    final = dict(state.get("final_outputs", {}))
    final["optimised_plan"] = optimised_plan
    return {
        "final_outputs": final,
        "audit_log": [audit("assemble", "assembled_plan",
                            removed=len(removals), merged=len(merges),
                            generated=len(generated))],
    }
