# `src/nodes/` — The work nodes

## 1. Purpose

The 10 sequential **work nodes** (plus 2 auxiliary nodes, 2 routing functions, and one shared
math helper) that make up the agent's analysis pipeline. Each node is a pure function
`node(state) -> dict` that reads what it needs from the shared state and returns **only the keys
it changes**.

## 2. Why this folder exists

The spec models the agent as a graph of small, single-responsibility steps. One file per node
keeps each step independently readable, testable, and wireable in `src/graph.py`. Routing
functions and the coverage-math helper live beside the nodes that use them.

## 3. How it fits into the overall architecture

These nodes **are** the graph body. `src/graph.py` imports every function here and wires them
into the spine + 2 loops + 3 interrupts. Nodes reach the outside world only through
`src/tools/` (`call_tool`), do deterministic text work through `src/nlp/`, ask the LLM for
judgement through `src/llm.py`, and read/write long-term facts through `src/memory/`.

```
intake → coverage → redundancy → retrieval → scoring
   → [HITL1] → prioritisation → (coverage_floor_gate ⇄ revise) → [HITL2]
   → gap_gen → validation ⇄ (route_after_validation) → drop_failing → [HITL3]
   → assemble → report
```

## 4. Files inside the folder

`__init__.py`, `intake.py`, `coverage.py`, `redundancy.py`, `retrieval.py`, `scoring.py`,
`prioritisation.py`, `gap_generation.py`, `validation.py`, `assemble.py`, `report.py`,
`_coverage_model.py`.

## 5. Responsibilities of each file

| File | Function(s) | Reads (state) | Writes (state) | Reaches |
|------|-------------|---------------|----------------|---------|
| `intake.py` | `intake_node` | `suite_path`, `raw_suite` | `normalised_suite`, `conventions`, `tool_errors` | `tools.repo_reader`, `nlp.extraction.extract_entities` |
| `coverage.py` | `coverage_node`, `_is_risk` | `normalised_suite`, `risk_areas`, `project_id` | `coverage_map`, `coverage_gaps`, `projected_coverage` | `tools.test_management`, `nlp.similarity`, `_coverage_model` |
| `redundancy.py` | `redundancy_node` | `normalised_suite` | `redundancy_flags`, `flakiness_flags`, `slow_flags` | `tools.ci_history`, `nlp.clustering` |
| `retrieval.py` | `retrieval_node`, `json_brief` | `project_id`, `normalised_suite`, `approved_priority` | `retrieved_context`, `approved_priority`, `tool_errors` | `tools.vector_store`, `tools.test_management`, `memory.store` |
| `scoring.py` | `scoring_node`, `_deterministic_scorecard`, `_llm_scorecard`, `_clamp` | flags, `coverage_map`, `projected_coverage`, `normalised_suite` | `scorecard`, `tool_errors` | `llm.complete/extract_json/load_prompt` (`scoring_prompt`) |
| `prioritisation.py` | `prioritisation_node`, **`coverage_floor_gate`** (router), **`revise_node`**, `_surviving`, `_tier_for` | `normalised_suite`, `approved_removals`, `optimization_goal`, `coverage_map`, flags, `coverage_target` | `prioritised_plan`, `projected_coverage`, `revise_count` | `_coverage_model`, `hitl.interrupts.is_protected` |
| `gap_generation.py` | `gap_generation_node`, `_llm_draft_test`, `_draft_test`, `_slug`, `_strip_fences` | `coverage_gaps`, `conventions` | `generated_tests`, `gen_retry_count`, `needs_regen`, `tool_errors` | `llm.complete/load_prompt` (`gap_generation_prompt`) |
| `validation.py` | `validation_node`, **`route_after_validation`** (router), **`drop_failing_node`** | `generated_tests`, `validation_passed`, `gen_retry_count` | `generated_tests`, `validation_passed`, `needs_regen` | `tools.sandbox.validate` |
| `assemble.py` | `assemble_node` | `normalised_suite`, `approved_removals`, `redundancy_flags`, `prioritised_plan`, `approved_generated_tests`, `projected_coverage` | `final_outputs.optimised_plan` | — (deterministic) |
| `report.py` | `report_node` | `scorecard`, `coverage_*`, flags, `retrieved_context`, `tool_errors`, `project_id`, `approved_*` | `final_outputs` (all 4 deliverables) | `memory.save_decision`, `memory.record_flaky` |
| `_coverage_model.py` | `coverage_for`, `_unit_of` | (args) tests, removals, redundancy_flags | returns projected-coverage float | `config.COVERAGE_*` |

## 6. Inputs

The shared `TestOptimiserState` (and, for `_coverage_model`, explicit arguments). Upstream data
originates from `tools/` (suite, criteria, CI history) and human decisions from `hitl/`.

## 7. Outputs

State-key updates that accumulate into `final_outputs` (the four deliverables) plus append-only
`audit_log`/`tool_errors` entries. `report_node` also persists decisions/flaky tests to memory.

## 8. Dependencies

`src.config` (thresholds), `src.observability.audit`, `src.tools.*` (all external I/O via
`call_tool`), `src.nlp.*`, `src.llm`, `src.memory.store`, `src.hitl.interrupts.is_protected`.
No node imports an SDK, file, or HTTP client directly.

## 9. Which folders call/use it

`src/graph.py` (registers every node); `tests/` imports individual nodes/routers directly.

## 10. Which folders it calls/uses

`src/tools/`, `src/nlp/`, `src/llm.py`, `src/memory/`, `src/hitl/interrupts.py`, `prompts/`,
`src/nodes/_coverage_model.py`.

## 11. Runtime execution flow

```
intake      : read_tests() → normalise → extract_entities → isolate unparseable
coverage    : criteria ↔ tests similarity → gaps ranked by risk → projected_coverage
redundancy  : cluster near-dupes; CI history → flaky (fail_rate ≥ FLAKY_FAIL_RATE) / slow (≥ SLOW_TEST_SECONDS)
retrieval   : seed + query vector store; load protected/prior decisions from memory
scoring     : LLM 6-dimension scorecard (deterministic rubric fallback)
─ HITL1 approve_removals ─
prioritisation → coverage_floor_gate:
    projected < target ? → revise (pare least-valuable removal) → gate again (≤ MAX_REVISE_ITERS)
    else                 → hitl_priority
─ HITL2 approve_ranking ─
gap_gen → validation → route_after_validation:
    all valid            → hitl_generated
    invalid, retries<3   → gap_gen (gen_retry_count++)
    invalid, retries=3   → drop_failing → hitl_generated
─ HITL3 approve_tests ─
assemble → report → END
```

## 12. Common debugging locations

- **Wrong/empty coverage or gaps** → `coverage.py` + `nlp/similarity.py` thresholds.
- **Bad flaky/slow flags** → `redundancy.py` + `config.FLAKY_FAIL_RATE`/`SLOW_TEST_SECONDS` + CI history.
- **Floor breach not blocked / infinite revise** → `coverage_floor_gate`/`revise_node` and `MAX_REVISE_ITERS`.
- **Generation loop never ends** → `route_after_validation` + `MAX_GEN_RETRIES` (see `tests/test_validation_loop.py`).
- **Scores look invented** → `scoring._llm_scorecard` vs `_deterministic_scorecard`; "insufficient evidence" path.
- **Deliverables incomplete** → `assemble.py` / `report.py` and the state keys they read.
