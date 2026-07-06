"""
Node 6 — Risk-based Prioritisation  +  the Coverage-Floor Gate (Blocker #2).

prioritisation_node re-tiers the surviving suite (smoke/regression/full) by risk,
coverage value, and the optimization goal. coverage_floor_gate is a REAL routing
function that blocks any removal set projected below the coverage target; revise_node
pares back the least-valuable removal and loops back so the gate re-checks. Risk-area
tests are pinned and never removable.

Architecture position: Node 6 of 10 — Prioritisation; runs after HITL 1 (approve
removals), before HITL 2 (approve ranking). This module also holds two auxiliaries:
coverage_floor_gate (a ROUTER after prioritisation and revise) and revise_node (an AUX
node in the coverage-floor loop).
Called by: the graph (src/graph.py).
Data in: optimization_goal, normalised_suite, approved_removals, coverage_map,
slow_flags, redundancy_flags, coverage_target, risk_areas, project_id, revise_count.
Data out: prioritised_plan, projected_coverage, approved_removals, revise_count,
audit_log[+] (see each function).
"""

from src.config import DEFAULT_COVERAGE_TARGET, MAX_REVISE_ITERS
from src.observability import audit, get_logger
from src.nodes._coverage_model import coverage_for
from src.hitl.interrupts import is_protected

_log = get_logger("prioritisation")


def _surviving(state) -> list[dict]:
    """Return the tests still in the suite after approved removals.

    Purpose: filter out approved-removal ids so only surviving tests get tiered.
    Inputs: state — reads approved_removals, normalised_suite.
    Outputs: list of surviving test dicts.
    Side effects: None (pure).
    Called by: prioritisation_node.
    Calls: (none).
    """
    removed = set(state.get("approved_removals", []))
    return [t for t in state.get("normalised_suite", []) if t["id"] not in removed]


def _tier_for(test, state) -> tuple[str, str]:
    """Decide a test's tier (smoke/regression/full) and the reason.

    Purpose: assign risk-based tiering — protected/risk-area first (smoke), slow to full,
        criterion-covering to smoke, everything else to regression.
    Inputs: test (a test dict); state — reads coverage_map, slow_flags, risk_areas,
        project_id (the last two via is_protected).
    Outputs: (tier, reason) tuple.
    Side effects: reads protected-test memory via is_protected.
    Called by: prioritisation_node.
    Calls: is_protected.
    """
    tid = test["id"]
    # WHY: flatten coverage_map values into the set of all test ids that cover a criterion.
    covered = {t for ids in state.get("coverage_map", {}).values() for t in ids}
    slow_ids = {f["test_id"] for f in state.get("slow_flags", [])}
    # WHY: protected/risk-area tests must run early and often -> always smoke, checked first.
    if is_protected(tid, state):
        return "smoke", "risk-area / protected — must run early and often"
    # WHY: slow tests demote to full so they don't bloat smoke/regression runtimes.
    if tid in slow_ids:
        return "full", "slow — run less frequently to keep smoke/regression fast"
    # WHY: tests that cover a criterion are high-value -> smoke.
    if tid in covered:
        return "smoke", "covers an acceptance criterion"
    # WHY: default bucket for everything else.
    return "regression", "standard regression coverage"


def prioritisation_node(state) -> dict:
    """Re-tier the surviving suite and recompute projected coverage.

    Purpose: assign each surviving test a tier (smoke/regression/full) with a reason and
        recompute projected coverage with approved removals applied.
    Inputs: state — reads optimization_goal, normalised_suite, approved_removals,
        coverage_map, slow_flags, redundancy_flags, risk_areas, project_id.
    Outputs: dict with prioritised_plan, projected_coverage, audit_log[+].
    Side effects: reads protected-test memory (via _tier_for/is_protected); appends an
        audit log entry.
    Called by: the graph (src/graph.py).
    Calls: _surviving, _tier_for, coverage_for, audit.
    """
    goal = state.get("optimization_goal", "reliability")
    tiers = {"smoke": [], "regression": [], "full": []}
    ranking = []
    # WHY: tier every surviving test and record both the bucket and the human-readable
    # reason so HITL 2 can review the ranking.
    for t in _surviving(state):
        tier, reason = _tier_for(t, state)
        tiers[tier].append(t["id"])
        ranking.append({"test_id": t["id"], "tier": tier, "reason": reason})

    # WHY: recompute coverage WITH approved removals applied — this is what the floor gate
    # checks next.
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

    Purpose: ROUTER — decide whether the current removal set is acceptable or must be
        revised to protect the coverage floor.
    Inputs: state — reads coverage_target, normalised_suite, approved_removals,
        redundancy_flags, revise_count.
    Outputs: the next node name — "approve_ranking" or "revise" (str).
    Side effects: logs a warning if the revise cap is hit; writes no state.
    Called by: the graph (conditional edges after prioritisation and revise).
    Calls: coverage_for.
    """
    target = state.get("coverage_target", DEFAULT_COVERAGE_TARGET)
    projected = coverage_for(state.get("normalised_suite", []),
                             state.get("approved_removals", []),
                             state.get("redundancy_flags", []))
    # WHY: floor met -> proceed to HITL 2; this is the normal exit of the coverage loop.
    if projected >= target:
        return "approve_ranking"
    # WHY: defensive backstop — if revise has run MAX_REVISE_ITERS times without meeting
    # the floor, stop looping and proceed (guarantees termination). Never hit in practice.
    if state.get("revise_count", 0) >= MAX_REVISE_ITERS:
        _log.warning("coverage_floor_gate: revise cap (%d) hit at projected=%.2f < target=%.2f; "
                     "proceeding without further revision", MAX_REVISE_ITERS, projected, target)
        return "approve_ranking"
    # WHY: below floor and cap not reached -> route to revise to pare back a removal.
    return "revise"


def revise_node(state) -> dict:
    """Pare back the least-valuable removal so coverage climbs back over the floor.

    Reverts a removal whose coverage unit is otherwise uncovered (a unique test),
    never a risk-area/protected test. Loops back to the gate, which re-checks.

    Purpose: AUX node in the coverage-floor loop — restore the single removal that gains
        the most coverage, then loop back to the gate.
    Inputs: state — reads normalised_suite, approved_removals, redundancy_flags,
        revise_count, risk_areas, project_id.
    Outputs: dict with approved_removals (shrunk), projected_coverage (raised),
        revise_count (++), audit_log[+].
    Side effects: reads protected-test memory (via is_protected); appends an audit entry.
    Called by: the graph (routed to by coverage_floor_gate; loops back to the gate).
    Calls: coverage_for, is_protected, audit.
    """
    suite = state.get("normalised_suite", [])
    removals = list(state.get("approved_removals", []))
    flags = state.get("redundancy_flags", [])

    # WHY: search for the removal whose reversal restores the most coverage. `gain` is the
    # coverage delta from removing this id from the removals list (i.e. keeping the test).
    # Find the removal that, if reverted, restores the most coverage.
    best, best_gain = None, 0.0
    current = coverage_for(suite, removals, flags)
    for tid in removals:
        # WHY: never revert a protected test back INTO consideration here — protection is
        # about eligibility for removal; protected ids shouldn't be in removals anyway, so
        # skip them when picking what to restore.
        if is_protected(tid, state):
            continue
        # WHY: gain = coverage if this id were NOT removed, minus current coverage.
        gain = coverage_for(suite, [r for r in removals if r != tid], flags) - current
        if gain > best_gain:
            best, best_gain = tid, gain

    # WHY: revert only the single best removal per iteration so the loop converges gradually
    # and the gate re-checks after each step.
    if best is not None:
        removals.remove(best)
    projected = coverage_for(suite, removals, flags)
    # WHY: bump the loop counter that coverage_floor_gate uses as its termination backstop.
    revise_count = state.get("revise_count", 0) + 1
    return {
        "approved_removals": removals,
        "projected_coverage": projected,
        "revise_count": revise_count,
        "audit_log": [audit("revise", "reverted_removal", reverted=best,
                            projected_coverage=projected, iteration=revise_count)],
    }
