"""Coverage-floor gate safety test (Blocker #2) — the floor gate must block unsafe cuts.

Critical safety test (Blocker #2): feed a removal set that would breach the coverage target
and assert the gate routes to 'revise' and never lets it pass. Also assert risk-area tests
are never selected for removal.

Architecture position: tests/ = the safety net; this module is Blocker #2's guard. It
exercises coverage_floor_gate + revise_node (src/nodes/prioritisation.py) and is_protected
(src/hitl/interrupts.py) in isolation — proving the coverage-floor loop blocks floor
breaches, converges, and never sacrifices a pinned (risk-area) test.

Called by: pytest.

Data in: hand-built in-memory state dicts (no files read; the golden fixture is not used
here — that is test_graph_e2e's job).
Data out: none (pure assertions).
"""

from src.config import DEFAULT_COVERAGE_TARGET
from src.nodes.prioritisation import coverage_floor_gate, revise_node
from src.hitl.interrupts import is_protected

# WHY: a minimal 4-test suite — a login near-duplicate pair (shared coverage unit) plus two
# unique-unit tests (checkout, payment). This lets us prove removing duplicates is "free"
# but removing unique units breaches the floor.
SUITE = [
    {"id": "test_login_success"},
    {"id": "test_login_success_duplicate"},
    {"id": "test_checkout_total"},
    {"id": "test_payment_gateway"},
]
CLUSTERS = [{"cluster": ["test_login_success", "test_login_success_duplicate"]}]

# WHY: the redundancy cluster marks the two login tests as the same coverage unit, so the
# coverage model treats removing one of them as costing nothing (its partner still covers
# the unit) — mirroring how redundancy_flags feed the projected-coverage math at runtime.


def _state(removals):
    """Build a minimal state dict for exercising the floor gate / revise node.

    Purpose: assemble the exact state keys coverage_floor_gate, revise_node, and
        is_protected read, with a given approved_removals set.
    Inputs: removals (iterable of test ids proposed for removal).
    Outputs: a TestOptimiserState-shaped dict (suite, clusters, target, risk_areas,
        approved_removals).
    Side effects: None (pure).
    Called by: every test in this module.
    Calls: list.
    """
    return {
        "normalised_suite": SUITE,
        "redundancy_flags": CLUSTERS,
        "coverage_target": DEFAULT_COVERAGE_TARGET,
        "risk_areas": ["payment"],
        "approved_removals": list(removals),
    }


def test_gate_blocks_floor_breaching_removals():
    """Purpose: the gate MUST route to 'revise' when removals project below the target.

    Validates the core Blocker #2 invariant: a floor-breaching removal set cannot pass.
    Inputs: state removing two unique-unit tests (checkout + payment).
    Outputs: None; asserts coverage_floor_gate returns "revise".
    Side effects: None (pure).
    Called by: pytest.
    Calls: _state, coverage_floor_gate.
    """
    # WHY: a floor-breaching set must route to revise — the gate is a real routing node,
    # not a warning; removing two unique coverage units drops projected coverage below 0.80.
    state = _state(["test_checkout_total", "test_payment_gateway"])
    assert coverage_floor_gate(state) == "revise"


def test_gate_passes_when_only_duplicate_removed():
    """Purpose: the gate MUST allow a removal that costs no coverage.

    Validates that removing one member of a redundancy cluster (shared unit) keeps
    projected coverage at/above target, so the gate approves the ranking.
    Inputs: state removing only the login duplicate.
    Outputs: None; asserts coverage_floor_gate returns "approve_ranking".
    Side effects: None (pure).
    Called by: pytest.
    Calls: _state, coverage_floor_gate.
    """
    # WHY: removing a redundant duplicate is free — its cluster partner still covers the
    # unit — so coverage is unchanged and the gate should let the plan through.
    state = _state(["test_login_success_duplicate"])
    assert coverage_floor_gate(state) == "approve_ranking"


def test_revise_recovers_until_gate_passes():
    """Purpose: the coverage-floor loop MUST converge — revise restores coverage to target.

    Validates that iterating gate -> revise terminates and ends with projected coverage at
    or above the target (the loop always exits; the run cannot spin forever).
    Inputs: state removing two unique-unit tests (a breach).
    Outputs: None; asserts the gate finally approves and coverage >= target.
    Side effects: mutates the local state dict via revise_node's returned deltas.
    Called by: pytest.
    Calls: _state, coverage_floor_gate, revise_node, dict.update.
    """
    state = _state(["test_checkout_total", "test_payment_gateway"])
    # WHY: loop revise until the gate stops asking for it; the bounded range doubles as a
    # test-side guard that the loop terminates (revise reverts the best removal each pass).
    for _ in range(10):
        if coverage_floor_gate(state) != "revise":
            break
        state.update(revise_node(state))
    assert coverage_floor_gate(state) == "approve_ranking"
    assert state["projected_coverage"] >= DEFAULT_COVERAGE_TARGET


def test_risk_area_tests_are_pinned():
    """Purpose: risk-area tests MUST be protected; non-matching tests MUST not be.

    Validates is_protected: a test whose id matches a declared risk area ("payment") is
    pinned (never removable); an unrelated test is not.
    Inputs: state with risk_areas=["payment"].
    Outputs: None; asserts is_protected is True for the payment test, False for login.
    Side effects: None (pure; memory store is empty via the isolated_memory fixture).
    Called by: pytest.
    Calls: _state, is_protected.
    """
    # WHY: risk-area tests must never be eligible for removal — this is the pinning rule
    # that makes the agent "recommend, never delete" safe for critical paths.
    state = _state([])
    assert is_protected("test_payment_gateway", state) is True
    assert is_protected("test_login_success", state) is False


def test_revise_never_reverts_into_a_pinned_removal():
    """Purpose: revise MUST recover coverage via non-pinned tests, not pinned ones.

    Validates that when a pinned test is (wrongly) present in removals, revise reverts a
    non-pinned removal first, leaving the pinned one for explicit human handling.
    Inputs: state removing both checkout (non-pinned) and payment (pinned).
    Outputs: None; asserts checkout is reverted out of approved_removals.
    Side effects: mutates the local state dict via revise_node's returned deltas.
    Called by: pytest.
    Calls: _state, revise_node, dict.update.
    """
    # WHY: even if a pinned test is wrongly in removals, revise won't keep a breach by
    # reverting non-pinned ones; the pinned one is left for explicit human handling.
    state = _state(["test_checkout_total", "test_payment_gateway"])
    state.update(revise_node(state))
    # WHY: checkout (non-pinned) is the removal reverted first, not payment (pinned).
    assert "test_checkout_total" not in state["approved_removals"]
