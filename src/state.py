"""
The shared state object — the 'clipboard' passed through every node.

MUST CONTAIN:
- The TestOptimiserState TypedDict exactly as defined in the spec:
  * Inputs: project_id, raw_suite, optimization_goal, coverage_target,
    risk_areas, additional_context, run_mode.
  * Working state: normalised_suite, coverage_map, projected_coverage,
    coverage_gaps, redundancy_flags, flakiness_flags, retrieved_context, scorecard.
  * Human decisions: approved_removals, approved_priority, approved_generated_tests.
  * Loop/error control: gen_retry_count, tool_errors (append-only), needs_regen.
  * Results: prioritised_plan, generated_tests, final_outputs.
  * Observability: audit_log (append-only, use Annotated[list, add]).
Single source of truth for the data shape — every node imports from here.
"""
