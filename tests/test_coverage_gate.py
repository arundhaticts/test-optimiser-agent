"""
Critical safety test (Blocker #2): feed a removal set that would breach the
coverage target and assert the gate routes to 'revise' and never lets it pass.
Also assert risk-area tests are never selected for removal.
"""

from src.config import DEFAULT_COVERAGE_TARGET
from src.nodes.prioritisation import coverage_floor_gate, revise_node
from src.hitl.interrupts import is_protected

SUITE = [
    {"id": "test_login_success"},
    {"id": "test_login_success_duplicate"},
    {"id": "test_checkout_total"},
    {"id": "test_payment_gateway"},
]
CLUSTERS = [{"cluster": ["test_login_success", "test_login_success_duplicate"]}]


def _state(removals):
    return {
        "normalised_suite": SUITE,
        "redundancy_flags": CLUSTERS,
        "coverage_target": DEFAULT_COVERAGE_TARGET,
        "risk_areas": ["payment"],
        "approved_removals": list(removals),
    }


def test_gate_blocks_floor_breaching_removals():
    # Removing two unique units drops coverage below 0.80.
    state = _state(["test_checkout_total", "test_payment_gateway"])
    assert coverage_floor_gate(state) == "revise"


def test_gate_passes_when_only_duplicate_removed():
    # Removing a redundant duplicate costs no coverage (shared unit).
    state = _state(["test_login_success_duplicate"])
    assert coverage_floor_gate(state) == "approve_ranking"


def test_revise_recovers_until_gate_passes():
    state = _state(["test_checkout_total", "test_payment_gateway"])
    # Loop revise until the gate stops asking for it (must terminate).
    for _ in range(10):
        if coverage_floor_gate(state) != "revise":
            break
        state.update(revise_node(state))
    assert coverage_floor_gate(state) == "approve_ranking"
    assert state["projected_coverage"] >= DEFAULT_COVERAGE_TARGET


def test_risk_area_tests_are_pinned():
    state = _state([])
    assert is_protected("test_payment_gateway", state) is True
    assert is_protected("test_login_success", state) is False


def test_revise_never_reverts_into_a_pinned_removal():
    # Even if a pinned test is wrongly in removals, revise won't keep a breach by
    # reverting non-pinned ones; the pinned one is left for explicit human handling.
    state = _state(["test_checkout_total", "test_payment_gateway"])
    state.update(revise_node(state))
    # checkout (non-pinned) is reverted first, not payment.
    assert "test_checkout_total" not in state["approved_removals"]
