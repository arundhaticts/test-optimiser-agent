"""Assert the TestOptimiserState has every required field and the right types."""

from operator import add
from typing import get_type_hints, Annotated, get_origin, get_args

from src.state import TestOptimiserState

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

# Append-only fields MUST use Annotated[list, add] so writes accumulate.
APPEND_ONLY_FIELDS = {"tool_errors", "audit_log"}


def test_every_required_field_present():
    fields = set(TestOptimiserState.__annotations__)
    missing = EXPECTED_FIELDS - fields
    assert not missing, f"state is missing fields: {missing}"


def test_append_only_fields_use_add_reducer():
    hints = get_type_hints(TestOptimiserState, include_extras=True)
    for field in APPEND_ONLY_FIELDS:
        ann = hints[field]
        assert get_origin(ann) is Annotated, f"{field} must be Annotated"
        assert add in get_args(ann), f"{field} must use the `add` reducer"
