"""
Critical safety test (Blocker #1): force generation to always fail validation and
assert the loop stops after MAX_GEN_RETRIES, falling back to drop-and-flag.
"""

from src.config import MAX_GEN_RETRIES
from src.nodes import validation as validation_mod
from src.nodes.validation import route_after_validation
from src.graph import build_graph


def test_router_retries_then_drops():
    # Valid -> approve; invalid with retries left -> regenerate; exhausted -> drop.
    assert route_after_validation({"validation_passed": True}) == "approve_tests"
    assert route_after_validation({"validation_passed": False, "gen_retry_count": 1}) == "gap_gen"
    assert route_after_validation(
        {"validation_passed": False, "gen_retry_count": MAX_GEN_RETRIES}) == "drop_failing"


def test_loop_terminates_and_drops(monkeypatch):
    # Force the sandbox to reject every generated test.
    monkeypatch.setattr(validation_mod.sandbox, "validate",
                        lambda code, timeout=10.0: {"valid": False, "error": "forced"})

    graph = build_graph()
    cfg = {"configurable": {"thread_id": "loop-test"}}
    state = graph.invoke({
        "project_id": "loop-test",
        "suite_path": "sample_data/sample_suite",
        "optimization_goal": "coverage",
        "coverage_target": 0.80,
        "risk_areas": [],
        "run_mode": "automated",      # no human; loop runs unattended
        "gen_retry_count": 0,
        "audit_log": [], "tool_errors": [],
    }, config=cfg)

    # The run completed (no infinite loop) and capped attempts at MAX_GEN_RETRIES.
    assert "final_outputs" in state
    assert state["gen_retry_count"] <= MAX_GEN_RETRIES
    # Still-invalid generated tests were dropped + flagged, not silently kept.
    generated = state["final_outputs"]["generated_tests"]
    assert generated == [] or all(g.get("dropped") for g in generated if not g.get("valid"))
    events = {e["event"] for e in state["final_outputs"]["audit_log"]}
    assert "dropped_failing_tests" in events
