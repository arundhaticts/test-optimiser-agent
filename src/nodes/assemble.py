"""
Node 9 — Assemble Optimised Plan.

Pure assembly (no external calls): combines kept tests, approved removals/merges, the
tiering, and approved generated tests into one plan shown side-by-side with the current
suite. Writes final_outputs.optimised_plan.
"""

from src.observability import audit


def assemble_node(state) -> dict:
    suite = state.get("normalised_suite", [])
    removals = state.get("approved_removals", [])
    merges = [{"keep": f["keep"], "merge": f["redundant"]}
              for f in state.get("redundancy_flags", [])]
    plan = state.get("prioritised_plan", {})
    generated = state.get("approved_generated_tests", [])

    optimised_plan = {
        "current": {"total_tests": len(suite),
                    "test_ids": [t["id"] for t in suite]},
        "proposed": {
            "removed": removals,
            "merged": merges,
            "tiers": plan.get("tiers", {}),
            "generated": [g.get("id") for g in generated],
            "kept": [t["id"] for t in suite if t["id"] not in set(removals)],
        },
        "projected_coverage": state.get("projected_coverage"),
        "goal": plan.get("goal"),
    }

    final = dict(state.get("final_outputs", {}))
    final["optimised_plan"] = optimised_plan
    return {
        "final_outputs": final,
        "audit_log": [audit("assemble", "assembled_plan",
                            removed=len(removals), merged=len(merges),
                            generated=len(generated))],
    }
