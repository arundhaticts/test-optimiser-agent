# Project Structure — Test Optimiser Agent

Every file in the repo with a one-line note on what it does. Generated/installed dirs
(`.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `.pytest_cache/`, `logs/`, `outputs/`,
`.agent_memory/`) are omitted — they are build/runtime artifacts, not source.

```
test-optimiser-agent/
│
├── main.py                     CLI entrypoint: builds the graph, runs it, drives the 3 HITL prompts from stdin, writes outputs/.
├── api.py                      FastAPI bridge (demo backend): POST /runs, /runs/{id}/resume, GET /runs/{id}, /health. Thin shell over the graph; synchronous; recommend-only.
├── requirements.txt            Python dependencies (langgraph, google-genai, fastapi/uvicorn, pydantic, dotenv, pytest; optional ML/sqlite noted).
├── pytest.ini                  pytest configuration (test discovery / settings).
├── .env                        Local secrets/config (GEMINI_API_KEY, model + feature flags). Gitignored — never committed.
├── .gitignore                  Excludes secrets, venv, caches, logs, outputs, memory store, vector DB.
├── README.md                   Repo entry point: one-paragraph overview, quick start, links into docs/, project tree.
│
├── src/                        ── all agent logic ──
│   ├── __init__.py             Marks src as a package.
│   ├── state.py                TestOptimiserState TypedDict — the shared "clipboard" passed through every node (append-only audit_log/tool_errors).
│   ├── config.py               All thresholds, model names, and feature flags in one place; loads .env and injects truststore (corporate TLS).
│   ├── graph.py                Registers all nodes + edges + the 2 conditional loops + 3 interrupts; compiles the graph; make_checkpointer() (MemorySaver / SQLite).
│   ├── llm.py                  The single Google Gemini client: complete(), llm_available(), extract_json(), load_prompt(). Offline-safe; routed via call_tool.
│   ├── observability.py        Logging + structured append-only audit_log (per node) + rotating logs/agent.log; local-time timestamps.
│   │
│   ├── nodes/                  ── the 10 work nodes (+ aux) ──
│   │   ├── __init__.py         Package marker.
│   │   ├── intake.py           Node 1: parse + normalise the suite into one shape, extract entities; isolate unparseable tests.
│   │   ├── coverage.py         Node 2: map tests ↔ acceptance criteria; surface coverage gaps with similarity scores.
│   │   ├── redundancy.py       Node 3: cluster near-duplicates; flag flaky/slow tests from CI history (with evidence).
│   │   ├── retrieval.py        Node 4: pull prior-run context + protected/flaky memory before scoring (RAG).
│   │   ├── scoring.py          Node 5: score 6 health dimensions (LLM strict-JSON; deterministic rubric fallback).
│   │   ├── prioritisation.py   Node 6: re-tier surviving tests (smoke/regression/full) + coverage_floor_gate (Blocker #2) + revise_node (capped loop).
│   │   ├── gap_generation.py   Node 7: draft a test per gap (LLM; stub fallback); increments gen_retry_count.
│   │   ├── validation.py       Node 8: sandbox syntax/import check + route_after_validation (Blocker #1) + drop_failing_node.
│   │   ├── assemble.py         Node 9: build the side-by-side current-vs-proposed optimised plan.
│   │   ├── report.py           Node 10: render the 4 deliverables, tag addressed gaps, write decisions/flaky to memory.
│   │   └── _coverage_model.py  Shared projected-coverage math used by Node 2 and the floor gate (so both compute it identically).
│   │
│   ├── nlp/                    ── deterministic text backbone (offline fallback) ──
│   │   ├── __init__.py         Package marker.
│   │   ├── embeddings.py       Embedding vectors: sentence-transformers if enabled, else a deterministic hashing vector.
│   │   ├── similarity.py       test↔criterion matching + gap detection (cosine when embeddings on; lexical overlap by default).
│   │   ├── clustering.py       Group near-duplicate tests above the duplicate threshold (single-linkage).
│   │   └── extraction.py       Tokenise/lemmatise/keyword + entity extraction (optional spaCy NER) + CI-log flaky/real triage.
│   │
│   ├── tools/                  ── external integrations, all via the retry/degrade wrapper ──
│   │   ├── __init__.py         Package marker.
│   │   ├── tool_wrapper.py     call_tool(): retry transient / no-retry fatal / degrade to a uniform envelope (Blocker #3); defines Transient/FatalError.
│   │   ├── repo_reader.py      Read the test suite + source; detect conventions. Unreadable repo = fatal halt.
│   │   ├── test_parser.py      Parse a suite into the internal shape (pytest via AST; junit/jest/cypress stubbed).
│   │   ├── coverage_parser.py  Parse a coverage report, with a static call-graph fallback estimate.
│   │   ├── ci_history.py       Read CI run stats (runs/fails/avg_seconds) — from sample_data/mock_ci_history.json (fixed path).
│   │   ├── test_management.py  Read acceptance criteria — from sample_data/sample_criteria.json (fixed path; stands in for Jira/Xray).
│   │   ├── vector_store.py     Chroma upsert/query for retrieval; degrades to empty context if unavailable.
│   │   └── sandbox.py          Subprocess syntax/import check for generated tests — never runs against production.
│   │
│   ├── hitl/                   ── human-in-the-loop ──
│   │   ├── __init__.py         Package marker.
│   │   └── interrupts.py       The 3 interrupt() checkpoints (approve removals/ranking/tests), evidence payloads, risk-area pinning; unwraps the resume envelope.
│   │
│   └── memory/                 ── long-term per-project store ──
│       ├── __init__.py         Package marker.
│       └── store.py            Per-project JSON store: prior decisions (never re-suggest a reject), protected + known-flaky tests.
│
├── prompts/                    ── LLM prompt templates ──
│   ├── scoring_prompt.md        Instructs the model to score the 6 dimensions as strict JSON ("insufficient evidence" when no data).
│   ├── prioritisation_prompt.md Instructs re-tiering by goal/risk, returning structured JSON (reserved for LLM-assisted tiering).
│   └── gap_generation_prompt.md Instructs writing one runnable, convention-matching test per gap.
│
├── sample_data/                ── synthetic fixture (generated) ──
│   ├── generate_sample_data.py  Single source of truth: declares the planted facts and writes the suite + CI + criteria + golden + README.
│   ├── sample_suite/            The test suite the agent analyses (23 pytest tests across 5 files):
│   │   ├── test_auth.py             login / logout / session / sign-up (holds one planted duplicate pair).
│   │   ├── test_cart.py             add / remove / totals / discounts (holds the second duplicate pair).
│   │   ├── test_checkout.py         orders / payment / retries (flaky + slow + risk-pinned tests live here).
│   │   ├── test_search.py           search / export / pagination (a flaky and a slow test here).
│   │   └── test_account.py          profile / email / deletion.
│   ├── mock_ci_history.json     Per-test runs/fails/avg_seconds — drives flaky/slow detection.
│   ├── sample_criteria.json     Acceptance criteria AC-1..AC-7 (AC-6/AC-7 are the planted gaps).
│   ├── expected_findings.json   GOLDEN answer key (duplicates/flaky/slow/gaps) — asserted by the e2e test; never read at runtime.
│   └── README.md                Detailed explainer: how the data is generated, each file, and what the frontend/agent reads.
│
├── tests/                      ── unit + e2e (the safety net) ──
│   ├── conftest.py              Isolates the memory store to a temp dir per test.
│   ├── test_state.py            Asserts the state schema has the expected fields/types.
│   ├── test_coverage_gate.py    Blocker #2: a floor-breaching removal set must route to revise; risk-area tests never removed.
│   ├── test_validation_loop.py  Blocker #1: always-failing validation stops after MAX_GEN_RETRIES and drops+flags.
│   └── test_graph_e2e.py        Full run on the fixture, auto-answering the 3 interrupts; asserts findings match expected_findings.json.
│
├── learning/                   ── standalone LangGraph tutorials (learn the mechanics first) ──
│   ├── 01_counter_graph.py      State + linear nodes.
│   ├── 02_conditional_branch.py Routing + loop (the gate/validation pattern).
│   └── 03_interrupt_resume.py   Checkpointer + interrupt() (the HITL pattern).
│
├── docs/                       ── documentation ──
│   ├── AGENT_SPEC.md            Canonical design: ADLC, autonomy, node-by-node, state schema, blocker fixes, safety controls.
│   ├── CLAUDE.md                Guide for AI coding assistants: rules/invariants, file map, conventions.
│   ├── PROJECT_HANDOFF.md       Phase-by-phase build status and how to resume.
│   ├── INSTALL.md               Full copy-paste setup (prereqs, venv, .env, sample data, runs, web UI, error fixes).
│   ├── CONFIGURATION.md         Every config knob + tuning per goal + data-input/TLS/persistence notes.
│   ├── OUTPUTS.md               Field-by-field reference for the 4 output deliverables (real emitted JSON).
│   ├── STRUCTURE.md             This file — the annotated file map.
│   ├── architecture.svg         End-to-end architecture diagram (browser → API → graph → tools/NLP/LLM → data/outputs).
│   └── architecture.min.svg     Minified copy of the architecture diagram.
│
└── frontend/                   ── React demo UI (Vite + TypeScript) ──
    ├── index.html               The single HTML page; React mounts into its <div id="root">.
    ├── package.json             Frontend dependencies + npm scripts (dev/build/lint).
    ├── package-lock.json        Locked dependency versions.
    ├── vite.config.ts           Vite build/dev config.
    ├── tsconfig*.json           TypeScript compiler settings (app/node/base).
    ├── eslint.config.js         Lint rules.
    ├── public/                  Static assets served as-is (favicon.svg, icons.svg).
    └── src/                     ── frontend source ──
        ├── main.tsx             Entry point: mounts <App> and imports global CSS.
        ├── App.tsx              The "brain": state machine (input→running→hitl→results) + audit polling; owns all state.
        ├── api.ts               All HTTP to the backend; normalises backend shapes (run_id/awaiting_approval) to clean types.
        ├── types.ts             TypeScript interfaces for every request/payload/output (compile-time contract; no runtime code).
        ├── index.css            All styling (dark theme, layout, badges, score colours, tooltip).
        ├── App.css              Leftover scaffold stylesheet (not imported; can be removed).
        ├── assets/              Scaffold images (react.svg, vite.svg, hero.png) — not used by the app.
        └── components/          ── UI pieces ──
            ├── InputPanel.tsx       Start form (suite/goal/coverage/risk/run-mode) → starts a run.
            ├── AuditLog.tsx         Live "Progress" feed; translates raw audit events into plain English.
            ├── DegradedBanner.tsx   Dismissible notice when the run used deterministic fallbacks (tool_errors).
            ├── hitl/                The 3 approval cards:
            │   ├── ApproveRemovals.tsx  Checkpoint 1 — flaky/duplicate candidates (pinned tests locked).
            │   ├── ApproveRanking.tsx   Checkpoint 2 — confirm smoke/regression/full tiers.
            │   └── ApproveTests.tsx     Checkpoint 3 — choose which generated tests to keep.
            └── results/             The 4 result tabs:
                ├── ResultsTabs.tsx      Tab switcher.
                ├── HealthScorecard.tsx  Tab 1 — six 0–10 dimension scores (null = "needs data").
                ├── CoverageMap.tsx      Tab 2 — criteria coverage + gaps (shows "gap · test drafted").
                ├── RedundancyReport.tsx Tab 3 — duplicates / flaky (fail-rate bar) / slow.
                └── OptimisedPlan.tsx    Tab 4 — current vs proposed plan (tiers, removals, generated).
```