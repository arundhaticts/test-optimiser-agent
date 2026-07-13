# Test Optimiser Agent

## Purpose
An L3, goal-driven agent that analyses an existing test suite and produces an optimised, re-prioritised test plan — scoring suite health, mapping coverage against acceptance criteria, flagging redundant/flaky/slow/obsolete tests, and drafting tests for real gaps. It **recommends, never deletes**, pausing for human approval at three checkpoints.

## Framework
LangGraph

## Tools
- `read_tests`: reads test files under a path into normalised test dicts.
- `read_source`: reads source-code text so coverage can be mapped against it.
- `detect_conventions`: infers the suite's style/conventions to guide gap-test drafting.
- `parse`: parses a test file across pytest/JUnit/Jest/Cypress formats into structured test records.
- `get_history`: returns CI pass/fail history for a single `test_id`.
- `all_history`: returns the full CI history map for the suite.
- `get_acceptance_criteria`: fetches the acceptance criteria for a project (test-management source).
- `get_known_issues`: fetches known issues / flaky-test list for a project.
- `validate`: syntax/import-checks generated test code in an isolated sandbox (never runs against production).
- `upsert`: stores a text + metadata record in the local vector store for later retrieval.
- `query`: semantic top-k retrieval of prior-run context from the vector store.
- `call_tool`: universal tool wrapper — every external/tool/SDK/file/HTTP call is routed through it with retries, backoff, and degraded-mode error capture.

## Workflow
The analysis spine is linear with three human-in-the-loop gates and two bounded loops. First `intake` normalises the suite; then `coverage` maps tests to acceptance criteria and finds gaps; `redundancy` flags near-duplicates, flaky, and slow tests; `retrieval` pulls prior-run memory; and `scoring` rates six health dimensions (LLM judgement with a deterministic offline fallback). The graph then hits **HITL checkpoint 1 (approve_removals)**, pausing until a human decides which flaky/duplicate tests may be quarantined/merged/removed — risk-area tests are pinned as protected and are never eligible.

Next, `prioritisation` re-tiers the surviving suite into smoke/regression/full. A real **coverage-floor gate** node then checks the projected coverage of the proposed change set: if it would fall below the coverage target, it routes to `revise` and loops back, and only once the change set clears the floor does it proceed to **HITL checkpoint 2 (approve_ranking)**.

After the ranking is approved, `gap_generation` drafts tests for the real gaps (LLM). Each draft goes to `validation`, which syntax/import-checks it in the sandbox; if validation fails, it loops back to `gap_generation` and retries **up to 3 times (MAX_GEN_RETRIES)**, after which `drop_failing` discards any still-invalid drafts so the run always terminates. The surviving drafts reach **HITL checkpoint 3 (approve_tests)**, where a human accepts which generated tests enter the plan. Finally `assemble` builds the side-by-side optimised plan and `report` renders the four JSON deliverables, writes outcomes to long-term memory, and the graph reaches END. In `automated` run mode the HITL checkpoints auto-resolve; in `interactive` mode they block for a decision.

## State
- `project_id` (str): memory key for long-term store lookups and per-project decisions.
- `suite_path` (str): filesystem path to the test suite that intake parses.
- `raw_suite` (list[dict]): tests supplied inline as an alternative to `suite_path`.
- `optimization_goal` (Literal["speed","coverage","reliability","cost"]): the goal driving prioritisation.
- `coverage_target` (float): the hard coverage floor (default 0.80) enforced by the coverage-floor gate.
- `risk_areas` (list[str]): areas whose tests are pinned as protected and never removed.
- `additional_context` (str): reserved free-text context.
- `run_mode` (Literal["interactive","automated"]): whether HITL checkpoints block or auto-resolve.
- `normalised_suite` (list[dict]): parsed/normalised suite produced by intake.
- `conventions` (dict): detected suite style used for gap generation.
- `coverage_map` (dict): criterion_id → covered test_ids.
- `projected_coverage` (float): coverage if the proposed changes were applied (recomputed on revise).
- `coverage_gaps` (list[dict]): uncovered paths/criteria ranked by risk.
- `redundancy_flags` (list[dict]): near-duplicate merge candidates.
- `flakiness_flags` (list[dict]): flaky tests with supporting evidence.
- `slow_flags` (list[dict]): tests over the slow-time threshold.
- `retrieved_context` (list[dict]): RAG results with relevance scores.
- `scorecard` (dict): per-dimension score + reason + action across six health dimensions.
- `approved_removals` (list[str]): tests a human approved for quarantine/merge/removal (HITL 1).
- `approved_priority` (dict): the tiering a human approved (HITL 2).
- `approved_generated_tests` (list[dict]): generated drafts a human accepted (HITL 3).
- `gen_retry_count` (int): bounds the validation→gap_generation loop (caps at MAX_GEN_RETRIES).
- `revise_count` (int): bounds the coverage-floor revise loop (defensive).
- `validation_passed` (bool): set by validation, read by the post-validation router.
- `needs_regen` (bool): informational flag from gap generation / validation.
- `tool_errors` (Annotated[list[dict], add]): append-only log of degraded/failed tool calls.
- `prioritised_plan` (dict): tiers + ranking + goal from prioritisation.
- `generated_tests` (list[dict]): drafts plus validity from gap generation/validation.
- `final_outputs` (dict): the four deliverables assembled and reported.
- `audit_log` (Annotated[list[dict], add]): append-only audit trail every node writes to.

## Configuration
- Model: `gemini-2.5-flash` (Google Gemini via the `google-genai` SDK; `REASONING_MODEL` and `FAST_MODEL`, both env-overridable).
- Temperature: default (unset — the SDK default is used; no explicit temperature is configured).
- Embedding model: `all-MiniLM-L6-v2` (`EMBEDDING_MODEL`, env-overridable).
- `OFFLINE_MODE`: `1`/`0` — auto-enabled when no `GEMINI_API_KEY` is present; forces deterministic fallbacks with no API calls.
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`): enables LLM judgement; optional (runs fully offline without it).
- `CHECKPOINT_DB`: optional SQLite path for durable, resumable paused runs (in-memory saver otherwise).
- Thresholds (from `src/config.py`): `MAX_GEN_RETRIES=3`, `DEFAULT_COVERAGE_TARGET=0.80`, `CRITERIA_MATCH_THRESHOLD=0.45`, `DUPLICATE_THRESHOLD=0.80`, `GAP_THRESHOLD=0.45`, `FLAKY_FAIL_RATE=0.10`, `SLOW_TEST_SECONDS=10.0`, `TOOL_RETRIES=3`, `BACKOFF_BASE=2`.

## Dependencies
- `google-genai` — Gemini LLM client (scoring rationale, gap-test drafting).
- `sentence-transformers` — semantic embeddings / similarity (optional).
- `spacy` — tokenise, lemmatise, NER, keyword extraction (optional).
- `scikit-learn` — clustering + TF-IDF for log triage.
- `chromadb` — local vector store for retrieval (optional).
- `pydantic` — request/response models for the HTTP bridge.
- `python-dotenv` — loads `.env` configuration.
- `fastapi` — HTTP bridge (`POST /runs`, `POST /runs/{id}/resume`, `GET /runs/{id}`, `GET /health`).
- `uvicorn` — ASGI server for the API.
- `pytest` — runtime dependency for sandbox validation and the `tests/` suite.
- `langgraph-checkpoint-sqlite` — optional; only needed when `CHECKPOINT_DB` is set for durable runs.
