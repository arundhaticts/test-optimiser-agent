"""Schema guard for TestOptimiserState — the shared state TypedDict every node uses.

Assert the TestOptimiserState has every required field and the right append-only reducers.

Architecture position: tests/ = the safety net; this module is the schema test. It locks
down the shape of the single "clipboard" (src/state.py) that flows through the graph so
that field drift (a renamed/removed key, or a lost append reducer) fails loudly here
rather than silently corrupting a run.

Called by: pytest.

Data in: reads TestOptimiserState.__annotations__ / type hints from src/state.py.
Data out: none (pure assertions).
"""

from operator import add
from typing import get_type_hints, Annotated, get_origin, get_args

from src.state import TestOptimiserState

# WHY: the canonical set of keys the state must expose, grouped by lifecycle role
# (inputs -> working -> decisions -> loop/error -> results -> observability). If a key
# is added/removed/renamed in src/state.py without updating this set, the test flags it.
EXPECTED_FIELDS = {
    # inputs
    "project_id", "raw_suite", "optimization_goal", "coverage_target",
    "risk_areas", "additional_context", "run_mode",
    # working state
    "normalised_suite", "coverage_map", "projected_coverage", "coverage_gaps",
    "redundancy_flags", "flakiness_flags", "retrieved_context", "scorecard",
    # human decisions
    "approved_removals", "approved_priority", "approved_generated_tests",
    # loop & error control
    "gen_retry_count", "validation_passed", "needs_regen", "tool_errors",
    # results
    "prioritised_plan", "generated_tests", "final_outputs",
    # observability
    "audit_log",
}

# WHY: audit_log and tool_errors are the two accumulating fields — every node contributes
# entries that must be appended, never overwritten. They MUST use Annotated[list, add] so
# LangGraph merges (concatenates) writes instead of last-writer-wins clobbering the trail.
APPEND_ONLY_FIELDS = {"tool_errors", "audit_log"}


def test_every_required_field_present():
    """Purpose: validate that state.py declares every field the pipeline depends on.

    Inputs: TestOptimiserState.__annotations__.
    Outputs: None; asserts EXPECTED_FIELDS is a subset of the declared annotations.
    Side effects: None (pure).
    Called by: pytest.
    Calls: set, TestOptimiserState.__annotations__.
    """
    # WHY: compare the declared keys against the required set; any missing key means a
    # node reads/writes a field the schema no longer guarantees.
    fields = set(TestOptimiserState.__annotations__)
    missing = EXPECTED_FIELDS - fields
    assert not missing, f"state is missing fields: {missing}"


def test_append_only_fields_use_add_reducer():
    """Purpose: validate the append-only invariant — audit_log and tool_errors accumulate.

    Inputs: resolved type hints of TestOptimiserState (with extras kept).
    Outputs: None; asserts each append-only field is Annotated[list, add].
    Side effects: None (pure).
    Called by: pytest.
    Calls: typing.get_type_hints, get_origin, get_args.
    """
    # WHY: include_extras=True keeps the Annotated wrapper so the reducer metadata (the
    # `add` operator) is visible; without it the hints collapse to bare `list`.
    hints = get_type_hints(TestOptimiserState, include_extras=True)
    for field in APPEND_ONLY_FIELDS:
        ann = hints[field]
        # WHY: an append-only field must be Annotated (carrying reducer metadata) and the
        # metadata must be `operator.add`, which is how LangGraph concatenates list writes.
        assert get_origin(ann) is Annotated, f"{field} must be Annotated"
        assert add in get_args(ann), f"{field} must use the `add` reducer"
