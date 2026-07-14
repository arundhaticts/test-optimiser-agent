"""
The shared state object — the 'clipboard' passed through every node.

This is the single source of truth for the data shape. Every node imports
TestOptimiserState from here, reads what it needs, and returns ONLY the keys it
updates (LangGraph merges them). Append-only fields use Annotated[list, add] so
iterative writes accumulate instead of overwriting.

Architecture position: shared clipboard — the one typed dict that flows through the
    entire graph. Not executable logic; a schema imported cross-cuttingly.
Called by: src/graph.py (parametrises StateGraph); every node/router/HITL function
    that takes `state: TestOptimiserState` and returns a partial-update dict.
Data in: inputs seeded by main.initial_state / api request (project_id, suite_path,
    optimization_goal, coverage_target, risk_areas, run_mode, additional_context,
    gen_retry_count=0, audit_log=[], tool_errors=[]).
Data out: working state, human decisions, loop/error control, and results filled in
    as the graph runs; final_outputs plus the append-only audit_log/tool_errors are
    what the entrypoints return and write.
"""

from typing import TypedDict, Annotated, Literal
from operator import add


class TestOptimiserState(TypedDict, total=False):
    """Purpose: define the shape of the single state dict shared by every node.

    This is the shared state (the "clipboard"): a total=False TypedDict, so any key
    may be absent until a node writes it. Nodes read what they need and return only
    the keys they changed; LangGraph merges those partial dicts. `audit_log` and
    `tool_errors` are append-only (Annotated[list, add] reducer); all other fields are
    last-writer-wins. Field-level notes are the trailing `#` comments below.
    """
    # --- Inputs (seeded by main.initial_state / api request) ---
    project_id: str                       # memory key; read by retrieval/hitl/prioritisation/report
    suite_path: str                       # path to the test suite (intake parses it)
    raw_suite: list[dict]                 # tests as ingested (alternative to suite_path)
    optimization_goal: Literal["speed", "coverage", "reliability", "cost"]  # read by prioritisation
    coverage_target: float                # default 0.80; the hard floor read by coverage_floor_gate
    risk_areas: list[str]                 # pins protected tests (via is_protected)
    additional_context: str               # reserved free-text context
    run_mode: Literal["interactive", "automated"]   # webhook/API => automated; read by HITL nodes
    provider: str                         # optional per-run LLM provider (gemini|openai|groq); None => env default
    model: str                            # optional per-run model id; None => provider's default model
    criteria_path: str                    # optional path to an uploaded acceptance-criteria JSON (else fixture)
    ci_history_path: str                  # optional path to an uploaded CI-history JSON (else fixture)
    expected_findings_path: str           # optional path to an uploaded expected-findings (golden) JSON;
                                          # read by report for the benchmark (None=sample golden, ""=none)

    # --- Working state (written by nodes) ---
    normalised_suite: list[dict]          # parsed suite from intake; read by most downstream nodes
    conventions: dict                     # detected suite style (for gap generation)
    coverage_map: dict                    # criterion_id -> covered test_ids
    projected_coverage: float             # coverage if proposed changes applied (recomputed on revise)
    coverage_gaps: list[dict]             # uncovered paths/criteria, ranked by risk
    redundancy_flags: list[dict]          # near-duplicate merge candidates
    flakiness_flags: list[dict]           # flaky tests with evidence
    slow_flags: list[dict]                # tests over the slow-time threshold
    retrieved_context: list[dict]         # RAG results w/ relevance scores
    scorecard: dict                       # per-dimension score + reason + action (6 dimensions)

    # --- Human decisions (captured at interrupts) ---
    approved_removals: list[str]          # written by hitl_removals and revise; pinned tests excluded
    approved_priority: dict               # approved tiering (retrieval inits {}, hitl_priority sets)
    approved_generated_tests: list[dict]  # kept drafts (written by hitl_generated)

    # --- Loop & error control ---
    gen_retry_count: int                  # bounds the validation loop (caps at MAX_GEN_RETRIES)
    revise_count: int                     # bounds the coverage-floor revise loop (defensive)
    validation_passed: bool               # set by validation_node, read by router
    needs_regen: bool                     # informational flag from gap_gen/validation
    tool_errors: Annotated[list[dict], add]   # degraded/failed tool calls (append-only reducer)

    # --- Results ---
    prioritised_plan: dict                # tiers + ranking + goal from prioritisation
    generated_tests: list[dict]           # drafts + validity from gap_gen/validation
    final_outputs: dict                   # the 4 deliverables (assemble + report)

    # --- Observability (append-only) ---
    audit_log: Annotated[list[dict], add]  # every node appends one+ entries (append-only reducer)
    llm_usage: Annotated[list[dict], add]  # one record per real LLM call (append-only); [] offline
