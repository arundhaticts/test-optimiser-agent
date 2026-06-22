"""
The shared state object — the 'clipboard' passed through every node.

This is the single source of truth for the data shape. Every node imports
TestOptimiserState from here, reads what it needs, and returns ONLY the keys it
updates (LangGraph merges them). Append-only fields use Annotated[list, add] so
iterative writes accumulate instead of overwriting.
"""

from typing import TypedDict, Annotated, Literal
from operator import add


class TestOptimiserState(TypedDict, total=False):
    # --- Inputs ---
    project_id: str
    suite_path: str                       # path to the test suite (intake parses it)
    raw_suite: list[dict]                 # tests as ingested
    optimization_goal: Literal["speed", "coverage", "reliability", "cost"]
    coverage_target: float                # default 0.80
    risk_areas: list[str]
    additional_context: str
    run_mode: Literal["interactive", "automated"]   # webhook/API => automated

    # --- Working state (written by nodes) ---
    normalised_suite: list[dict]
    conventions: dict                     # detected suite style (for gap generation)
    coverage_map: dict                    # criterion_id -> covered test_ids
    projected_coverage: float             # coverage if proposed changes applied
    coverage_gaps: list[dict]             # uncovered paths/criteria, ranked by risk
    redundancy_flags: list[dict]
    flakiness_flags: list[dict]
    slow_flags: list[dict]                # tests over the slow-time threshold
    retrieved_context: list[dict]         # RAG results w/ relevance scores
    scorecard: dict                       # per-dimension score + reason + action

    # --- Human decisions (captured at interrupts) ---
    approved_removals: list[str]
    approved_priority: dict
    approved_generated_tests: list[dict]

    # --- Loop & error control ---
    gen_retry_count: int                  # bounds the validation loop
    revise_count: int                     # bounds the coverage-floor revise loop (defensive)
    validation_passed: bool               # set by validation_node, read by router
    needs_regen: bool
    tool_errors: Annotated[list[dict], add]   # degraded/failed tool calls

    # --- Results ---
    prioritised_plan: dict
    generated_tests: list[dict]
    final_outputs: dict

    # --- Observability (append-only) ---
    audit_log: Annotated[list[dict], add]
