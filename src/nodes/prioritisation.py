"""
Node 6 — Risk-based Prioritisation  +  the Coverage-Floor Gate (Blocker #2).

prioritisation_node re-tiers the surviving suite (smoke/regression/full) by risk,
coverage value, and the optimization goal. coverage_floor_gate is a REAL routing
function that blocks any removal set projected below the coverage target; revise_node
pares back the least-valuable removal and loops back so the gate re-checks. Risk-area
tests are pinned and never removable.
"""

from src.config import DEFAULT_COVERAGE_TARGET, MAX_REVISE_ITERS
from src.observability import audit, get_logger
from src.nodes._coverage_model import coverage_for
from src.hitl.interrupts import is_protected

_log = get_logger("prioritisation")


def _surviving(state) -> list[dict]:
    removed = set(state.get("approved_removals", []))
    return [t for t in state.get("normalised_suite", []) if t["id"] not in removed]


def _tier_for(test, state) -> tuple[str, str]:
    tid = test["id"]
    covered = {t for ids in state.get("coverage_map", {}).values() for t in ids}
    slow_ids = {f["test_id"] for f in state.get("slow_flags", [])}
    if is_protected(tid, state):
        return "smoke", "risk-area / protected — must run early and often"
    if tid in slow_ids:
        return "full", "slow — run less frequently to keep smoke/regression fast"
    if tid in covered:
        return "smoke", "covers an acceptance criterion"
    return "regression", "standard regression coverage"


def prioritisation_node(state) -> dict:
    goal = state.get("optimization_goal", "reliability")
    tiers = {"smoke": [], "regression": [], "full": []}
    ranking = []
    for t in _surviving(state):
        tier, reason = _tier_for(t, state)
        tiers[tier].append(t["id"])
        ranking.append({"test_id": t["id"], "tier": tier, "reason": reason})

    projected = coverage_for(state.get("normalised_suite", []),
                             state.get("approved_removals", []),
                             state.get("redundancy_flags", []))
    plan = {"tiers": tiers, "ranking": ranking, "goal": goal}
    return {
        "prioritised_plan": plan,
        "projected_coverage": projected,
        "audit_log": [audit("prioritisation", "tiered",
                            smoke=len(tiers["smoke"]), regression=len(tiers["regression"]),
                            full=len(tiers["full"]), projected_coverage=projected)],
    }


def coverage_floor_gate(state) -> str:
    """ENFORCED gate (Blocker #2): block any change set below the coverage target.

    Routes to `revise` while projected coverage is below target. A defensive cap
    (MAX_REVISE_ITERS) guarantees termination even if a future (non-monotonic) coverage
    parser fails to converge — today the deterministic model always recovers, so the cap
    is never reached.
    """
    target = state.get("coverage_target", DEFAULT_COVERAGE_TARGET)
    projected = coverage_for(state.get("normalised_suite", []),
                             state.get("approved_removals", []),
                             state.get("redundancy_flags", []))
    if projected >= target:
        return "approve_ranking"
    if state.get("revise_count", 0) >= MAX_REVISE_ITERS:
        _log.warning("coverage_floor_gate: revise cap (%d) hit at projected=%.2f < target=%.2f; "
                     "proceeding without further revision", MAX_REVISE_ITERS, projected, target)
        return "approve_ranking"
    return "revise"


def revise_node(state) -> dict:
    """Pare back the least-valuable removal so coverage climbs back over the floor.

    Reverts a removal whose coverage unit is otherwise uncovered (a unique test),
    never a risk-area/protected test. Loops back to the gate, which re-checks.
    """
    suite = state.get("normalised_suite", [])
    removals = list(state.get("approved_removals", []))
    flags = state.get("redundancy_flags", [])

    # Find the removal that, if reverted, restores the most coverage.
    best, best_gain = None, 0.0
    current = coverage_for(suite, removals, flags)
    for tid in removals:
        if is_protected(tid, state):
            continue
        gain = coverage_for(suite, [r for r in removals if r != tid], flags) - current
        if gain > best_gain:
            best, best_gain = tid, gain

    if best is not None:
        removals.remove(best)
    projected = coverage_for(suite, removals, flags)
    revise_count = state.get("revise_count", 0) + 1
    return {
        "approved_removals": removals,
        "projected_coverage": projected,
        "revise_count": revise_count,
        "audit_log": [audit("revise", "reverted_removal", reverted=best,
                            projected_coverage=projected, iteration=revise_count)],
    }
