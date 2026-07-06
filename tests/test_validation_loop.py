"""Validation-loop safety test (Blocker #1) — the generation loop must always terminate.

Critical safety test (Blocker #1): force generation to always fail validation and assert
the loop stops after MAX_GEN_RETRIES, falling back to drop-and-flag.

Architecture position: tests/ = the safety net; this module is Blocker #1's guard. It
checks the route_after_validation router directly and then drives a full graph run with the
sandbox monkeypatched to always fail — proving the gap_gen<->validation loop cannot spin
forever and that still-invalid drafts are dropped-and-flagged rather than silently kept.

Called by: pytest.

Data in: reads the real sample suite at sample_data/sample_suite (via build_graph -> intake)
for the end-to-end run; the sandbox is monkeypatched, so no drafts actually compile.
Data out: none persisted (memory is isolated by the conftest fixture); pure assertions.
"""

from src.config import MAX_GEN_RETRIES
from src.nodes import validation as validation_mod
from src.nodes.validation import route_after_validation
from src.graph import build_graph


def test_router_retries_then_drops():
    """Purpose: route_after_validation MUST branch valid->approve, fail->retry->drop.

    Validates the Blocker #1 routing invariant directly: all-valid routes to approve_tests;
    a failure with retries left routes back to gap_gen; a failure at MAX_GEN_RETRIES routes
    to drop_failing (so the loop cannot exceed the cap).
    Inputs: three synthetic state dicts (validation_passed / gen_retry_count combos).
    Outputs: None; asserts the returned next-node string for each case.
    Side effects: None (pure).
    Called by: pytest.
    Calls: route_after_validation.
    """
    # WHY: exercise each branch of the router — valid, retryable failure, exhausted retries
    # — so the loop's exit conditions are pinned independently of a full graph run.
    assert route_after_validation({"validation_passed": True}) == "approve_tests"
    assert route_after_validation({"validation_passed": False, "gen_retry_count": 1}) == "gap_gen"
    assert route_after_validation(
        {"validation_passed": False, "gen_retry_count": MAX_GEN_RETRIES}) == "drop_failing"


def test_loop_terminates_and_drops(monkeypatch):
    """Purpose: a full run with an always-failing sandbox MUST terminate and drop+flag.

    Validates Blocker #1 end to end: with validation forced to reject every draft, the
    gap_gen<->validation loop caps at MAX_GEN_RETRIES, the run reaches final_outputs
    (no infinite loop), still-invalid drafts are dropped (not silently kept), and a
    'dropped_failing_tests' audit event is recorded.
    Inputs: monkeypatch (to stub the sandbox); the real sample suite via build_graph.
    Outputs: None; asserts on the final_outputs (retry count, generated_tests, audit log).
    Side effects: graph invocation (runs the whole pipeline in automated mode); spawns no
        real sandbox subprocess (validate is stubbed); memory writes isolated by conftest.
    Called by: pytest.
    Calls: monkeypatch.setattr, build_graph, graph.invoke.
    """
    # WHY: the monkeypatched failing sandbox — force sandbox.validate to reject every
    # generated test so the loop is guaranteed to fail on every pass, exposing whether the
    # MAX_GEN_RETRIES cap and drop_failing fallback actually fire.
    monkeypatch.setattr(validation_mod.sandbox, "validate",
                        lambda code, timeout=10.0: {"valid": False, "error": "forced"})

    graph = build_graph()
    # WHY: thread_id namespaces this run's checkpoints so the automated run is independent.
    cfg = {"configurable": {"thread_id": "loop-test"}}
    # WHY: run_mode="automated" auto-approves every HITL checkpoint so the loop runs
    # unattended — the test can drive a full run without answering interrupts.
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

    # WHY: reaching final_outputs proves the run terminated — the loop did not spin — and
    # the retry counter never exceeded the cap (drop_failing must have taken over).
    assert "final_outputs" in state
    assert state["gen_retry_count"] <= MAX_GEN_RETRIES
    # WHY: any draft that stayed invalid must be explicitly flagged "dropped", never kept
    # silently — the safety guarantee is drop-and-flag, not quiet acceptance.
    generated = state["final_outputs"]["generated_tests"]
    assert generated == [] or all(g.get("dropped") for g in generated if not g.get("valid"))
    # WHY: the drop_failing node must leave an audit trail so the human sees the fallback
    # was exercised — assert its headline event is present in the recorded audit log.
    events = {e["event"] for e in state["final_outputs"]["audit_log"]}
    assert "dropped_failing_tests" in events
