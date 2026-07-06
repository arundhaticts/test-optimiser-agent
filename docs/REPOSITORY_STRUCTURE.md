# Project Structure & Folder Walkthrough — Test Optimiser Agent

This document combines two views of the repository:

- **Part 1 — Annotated file map:** every file in the repo with a one-line note on what it does.
- **Part 2 — Folder walkthrough:** a guided, folder-by-folder tour (purpose, why it exists, how it
  interacts, execution path, key files/classes/functions, and demo/interview questions) written to
  be **presented to a manager**.

Generated/installed dirs (`.venv/`, `node_modules/`, `__pycache__/`, `dist/`, `.pytest_cache/`,
`logs/`, `outputs/`, `.agent_memory/`) are omitted from the tree — they are build/runtime
artifacts, not source (they are described in Part 2).

**Related deep-dives:** [ARCHITECTURE_DETAILED.md](ARCHITECTURE_DETAILED.md) ·
[EXECUTION_FLOW.md](EXECUTION_FLOW.md) · [DATA_FLOW.md](DATA_FLOW.md) ·
[STATE_FLOW.md](STATE_FLOW.md) · [FUNCTION_CALL_MAP.md](FUNCTION_CALL_MAP.md)

---

# Part 1 — Annotated file map

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
│   ├── STRUCTURE.md             This file — the annotated file map (Part 1) + folder walkthrough (Part 2).
│   ├── ARCHITECTURE_DETAILED.md Layered components, graph topology, module dependency graph, safety controls (Mermaid).
│   ├── EXECUTION_FLOW.md        Runtime order; per-node prev/next/in/out/tools/files; the two loops (Mermaid).
│   ├── DATA_FLOW.md             Inputs → transformations → outputs; tools + files per node; degrade paths (Mermaid).
│   ├── STATE_FLOW.md            Every TestOptimiserState field's read/write lifecycle; per-node input/output state (Mermaid).
│   ├── FUNCTION_CALL_MAP.md     Every function: defined in / called by / calls what / reads state / updates state.
│   ├── architecture.svg         End-to-end architecture diagram (browser → API → graph → tools/NLP/LLM → data/outputs).
│   └── architecture.min.svg     Minified copy of the architecture diagram.
│
├── frontend/                   ── React demo UI (Vite + TypeScript) ──
│   ├── README.md               Frontend-specific guide (React primer, structure, data flow).
│   ├── index.html               The single HTML page; React mounts into its <div id="root">.
│   ├── package.json             Frontend dependencies + npm scripts (dev/build/lint).
│   ├── package-lock.json        Locked dependency versions.
│   ├── vite.config.ts           Vite build/dev config.
│   ├── tsconfig*.json           TypeScript compiler settings (app/node/base).
│   ├── eslint.config.js         Lint rules.
│   ├── public/                  Static assets served as-is (favicon.svg, icons.svg).
│   └── src/                     ── frontend source ──
│       ├── main.tsx             Entry point: mounts <App> and imports global CSS.
│       ├── App.tsx              The "brain": state machine (input→running→hitl→results) + audit polling; owns all state.
│       ├── api.ts               All HTTP to the backend; normalises backend shapes (run_id/awaiting_approval) to clean types.
│       ├── types.ts             TypeScript interfaces for every request/payload/output (compile-time contract; no runtime code).
│       ├── index.css            All styling (dark theme, layout, badges, score colours, tooltip).
│       ├── App.css              Leftover scaffold stylesheet (not imported; can be removed).
│       ├── assets/              Scaffold images (react.svg, vite.svg, hero.png) — not used by the app.
│       └── components/          ── UI pieces ──
│           ├── InputPanel.tsx       Start form (suite/goal/coverage/risk/run-mode) → starts a run.
│           ├── AuditLog.tsx         Live "Progress" feed; translates raw audit events into plain English.
│           ├── DegradedBanner.tsx   Dismissible notice when the run used deterministic fallbacks (tool_errors).
│           ├── hitl/                The 3 approval cards:
│           │   ├── ApproveRemovals.tsx  Checkpoint 1 — flaky/duplicate candidates (pinned tests locked).
│           │   ├── ApproveRanking.tsx   Checkpoint 2 — confirm smoke/regression/full tiers.
│           │   └── ApproveTests.tsx     Checkpoint 3 — choose which generated tests to keep.
│           └── results/             The 4 result tabs:
│               ├── ResultsTabs.tsx      Tab switcher.
│               ├── HealthScorecard.tsx  Tab 1 — six 0–10 dimension scores (null = "needs data").
│               ├── CoverageMap.tsx      Tab 2 — criteria coverage + gaps (shows "gap · test drafted").
│               ├── RedundancyReport.tsx Tab 3 — duplicates / flaky (fail-rate bar) / slow.
│               └── OptimisedPlan.tsx    Tab 4 — current vs proposed plan (tiers, removals, generated).
│
├── logs/                       ── runtime artifact (gitignored) ──
│   └── agent.log                Rotating human-readable trace written by observability.audit() (2 MB × 3 backups).
│
└── outputs/                    ── runtime artifact (gitignored) ──
    ├── scorecard.json                    Deliverable 1 — six health-dimension scores.
    ├── coverage_gap_map.json             Deliverable 2 — coverage map + gaps + projected coverage.
    ├── redundancy_flakiness_report.json  Deliverable 3 — duplicates / flaky / slow flags.
    └── optimised_plan.json               Deliverable 4 — current-vs-proposed plan.
```

> **Note:** each source folder also carries its own `README.md` (root, `src/`, `src/nodes/`,
> `src/tools/`, `src/nlp/`, `src/memory/`, `src/hitl/`, `prompts/`, `tests/`, `learning/`,
> `logs/`, `outputs/`, `frontend/`) with the full 12-point folder contract. Part 2 below is the
> narrative, manager-facing companion to those.

---

# Part 2 — Folder walkthrough

A guided, folder-by-folder tour of the codebase, each section answers the same questions: what the folder is
for, why it exists, how it connects to the rest, a typical execution path, the key files/classes/
functions, and the questions you're most likely to be asked about it.

> **One-sentence summary of the product:** an L3, goal-driven LangGraph agent that takes an
> existing test suite and returns a leaner, re-prioritised plan — scoring health, mapping
> coverage, flagging redundant/flaky/slow tests, and drafting tests for real gaps — while
> **pausing for human approval at three checkpoints**. It *recommends, never deletes*, runs
> **offline by default**, and uses **Google Gemini** for judgement when a key is present.

**Related deep-dives:** [ARCHITECTURE_DETAILED.md](ARCHITECTURE_DETAILED.md) ·
[EXECUTION_FLOW.md](EXECUTION_FLOW.md) · [DATA_FLOW.md](DATA_FLOW.md) ·
[STATE_FLOW.md](STATE_FLOW.md) · [FUNCTION_CALL_MAP.md](FUNCTION_CALL_MAP.md) · Part 1 above.

---

## The 60-second map

```
                 ┌───────── how you drive it ─────────┐
   CLI (main.py) │              api.py (HTTP) ◀── frontend/ (React demo)
                 └───────────────┬────────────────────┘
                                 ▼
                        src/graph.py  (the compiled state machine)
                                 │
   ┌──────────── src/ = all the agent's logic ────────────────────────┐
   │ nodes/  → the 10-step analysis pipeline                          │
   │ tools/  → all external I/O (safe retry/degrade wrapper)          │
   │ nlp/    → deterministic matching / dedup / gap-finding           │
   │ hitl/   → the 3 human approval checkpoints                       │
   │ memory/ → what the agent remembers between runs                  │
   └──────────────────────────────────────────────────────────────────┘
        reads ▲ prompts/  sample_data/           writes ▼ outputs/  logs/
```

| Folder | In one line |
|--------|-------------|
| `/` (root) | The front door — entrypoints (`main.py`, `api.py`) and manifests |
| `src/` | All agent logic (state, graph, nodes, tools, nlp, hitl, memory) |
| `src/nodes/` | The 10-step analysis pipeline — the heart of the product |
| `src/tools/` | Every external call, behind one retry/degrade safety wrapper |
| `src/nlp/` | The deterministic "cheap brain" (works with no API key) |
| `src/hitl/` | The three human-approval pause points |
| `src/memory/` | Long-term memory across runs |
| `prompts/` | The instructions we give the LLM |
| `sample_data/` | A synthetic suite + a golden answer key for the demo/tests |
| `tests/` | The automated safety net for our non-negotiable rules |
| `frontend/` | The React demo UI |
| `learning/` | Standalone LangGraph tutorials (onboarding aid) |
| `logs/`, `outputs/` | Runtime artifacts — the trace and the deliverables |
| `docs/` | This documentation set |

---

## `/` (root) — the front door

- **Purpose.** Holds the two entrypoints that connect the agent to the world (`main.py` for the
  command line, `api.py` for HTTP) plus the dependency/test manifests.
- **Why it was created.** To separate *how you invoke the agent* from *what the agent does*. The
  same compiled graph is driven by a terminal, a web UI, or the test suite — no duplicated logic.
- **How it interacts.** `main.py`/`api.py` call `src/graph.py:build_graph()` and run it; `api.py`
  is what the `frontend/` talks to.
- **Typical execution path.** `main()` → `configure_logging()` → `build_graph()` →
  `graph.invoke(initial_state)` → answer 3 interrupts → `write_outputs()` → print summary.
- **Key files.** `main.py`, `api.py`, `requirements.txt`, `pytest.ini`, `.env` (gitignored).
- **Key functions.** `main.run()`, `main.write_outputs()`, `api._package()` (shapes each HTTP
  response as *awaiting approval* or *completed*).
- **Demo/interview questions:**
  - *How do you run it?* `python main.py --suite sample_data/sample_suite --goal speed`.
  - *CLI vs API — what's different?* Same graph; the CLI reads approvals from stdin, the API
    blocks each `POST` to the next checkpoint and resumes via a follow-up `POST`.
  - *Where do results go?* Four JSON files in `outputs/`, and the same objects returned over HTTP.

---

## `src/` — all agent logic

- **Purpose.** The whole agent as one importable package: the shared state schema, the compiled
  graph, the single LLM client, central config, observability, and the five sub-packages.
- **Why it was created.** Keep orchestration logic separate from entrypoints and from data/config
  assets, so it can be reused and tested independently.
- **How it interacts.** Imported by `main.py`, `api.py`, and `tests/`. Internally, a single typed
  **state object flows down** through the nodes; cross-cutting modules (`config`, `observability`,
  `llm`) are used almost everywhere.
- **Typical execution path.** `graph.py:build_graph()` compiles a `StateGraph` over
  `state.py:TestOptimiserState`, then invokes nodes in order.
- **Key files.** `state.py` (the shared "clipboard"), `config.py` (every threshold/flag/model —
  *no magic numbers anywhere else*), `graph.py` (wiring), `llm.py` (Gemini client),
  `observability.py` (logging + audit trail).
- **Key classes.** `TestOptimiserState` (TypedDict).
- **Key functions.** `build_graph()`, `make_checkpointer()`, `llm.complete()`,
  `observability.audit()`.
- **Demo/interview questions:**
  - *What is the "state"?* One dictionary passed through every step; each node returns only the
    keys it changed and LangGraph merges them.
  - *Where do the thresholds live?* All in `config.py` (flaky rate, slow seconds, coverage target,
    retry caps) — tunable in one place.
  - *Does it need an API key?* No — `OFFLINE_MODE` kicks in and deterministic fallbacks run.

---

## `src/nodes/` — the analysis pipeline (the heart)

- **Purpose.** The 10 sequential work steps (plus 2 auxiliary nodes and 2 routing functions) that
  do the actual analysis. Each is a small function `node(state) -> dict`.
- **Why it was created.** The design models the agent as a graph of single-responsibility steps —
  each independently readable, testable, and wireable.
- **How it interacts.** Registered by `src/graph.py`. Nodes reach the outside world *only* through
  `src/tools/`, do text work via `src/nlp/`, ask the LLM via `src/llm.py`, and remember via
  `src/memory/`.

- **What happens here (in order):**

  | # | Node | What it does | Key state it writes |
  |---|------|--------------|---------------------|
  | 1 | `intake` | parse & normalise the suite | `normalised_suite`, `conventions` |
  | 2 | `coverage` | map tests ↔ criteria, find gaps | `coverage_map`, `coverage_gaps`, `projected_coverage` |
  | 3 | `redundancy` | duplicates + flaky/slow from CI | `redundancy_flags`, `flakiness_flags`, `slow_flags` |
  | 4 | `retrieval` | pull prior-run context (RAG) | `retrieved_context` |
  | 5 | `scoring` | 6-dimension health scorecard | `scorecard` |
  | — | **HITL 1** | approve removals | `approved_removals` |
  | 6 | `prioritisation` (+ gate ⇄ `revise`) | re-tier smoke/regression/full; **block floor breaches** | `prioritised_plan`, `projected_coverage` |
  | — | **HITL 2** | approve ranking | `approved_priority` |
  | 7 | `gap_gen` | draft a test per gap | `generated_tests`, `gen_retry_count` |
  | 8 | `validation` (⇄ retry / `drop_failing`) | sandbox syntax-check drafts | `validation_passed` |
  | — | **HITL 3** | approve generated tests | `approved_generated_tests` |
  | 9 | `assemble` | build current-vs-proposed plan | `final_outputs.optimised_plan` |
  | 10 | `report` | render 4 deliverables + save memory | `final_outputs` |

- **Which files execute first / last?** First: `intake.py`. Last: `report.py`.
- **Which state keys are modified?** Effectively every working key — see the table above and
  [STATE_FLOW.md](STATE_FLOW.md) for the exhaustive read/write map.
- **Key functions.** `coverage_floor_gate` and `route_after_validation` (the two routers that make
  the loops terminate); `_coverage_model.coverage_for` (one coverage calculation shared by both
  the coverage node and the floor gate, so they can never disagree).
- **Demo/interview questions:**
  - *What's the "coverage-floor gate"?* A real routing node that refuses any removal set projected
    below the coverage target and loops through `revise` until it's safe.
  - *Why won't the generation loop run forever?* `route_after_validation` caps it at
    `MAX_GEN_RETRIES = 3`, then drops-and-flags the failing tests.
  - *Where's the "brain"?* `scoring` and `gap_gen` use the LLM; everything else is deterministic.

---

## `src/tools/` — external integrations (behind one safety wrapper)

- **Purpose.** Every point where the agent touches the outside world: reading the repo, parsing
  tests, loading criteria/CI history, the vector store, and the sandbox.
- **Why it was created.** So retries, degradation, and error surfacing are implemented **once**.
  A single flaky dependency must never crash the run.
- **How it interacts.** Called by nodes via `call_tool(fn, …)`; even LLM calls flow through it.
- **Typical execution path.** `node → call_tool(fn) → {ok, data|error}`; on failure the node
  records a `tool_error` and continues on a deterministic fallback.
- **Key files.** `tool_wrapper.py` (the contract), `repo_reader.py`/`test_parser.py` (AST parsing,
  *never executes tests*), `ci_history.py`, `test_management.py`, `vector_store.py`, `sandbox.py`.
- **Key classes.** `TransientError` (retry) and `FatalError` (don't retry); `VectorStore`.
- **Key functions.** `call_tool()`, `sandbox.validate()` (subprocess syntax check).
- **Demo/interview questions:**
  - *What if Gemini/Jira/CI is down?* The call degrades to a uniform envelope; the run still
    completes with a visible "degraded" note — this is the "recommend-safe" guarantee.
  - *Do generated tests ever run against production?* No. The sandbox only compiles them
    (syntax/import) in a subprocess.

---

## `src/nlp/` — the deterministic "cheap brain"

- **Purpose.** All matching, deduplication, gap detection, and log triage — embeddings,
  similarity, clustering, extraction.
- **Why it was created.** Structural questions ("does this test cover this criterion?", "are these
  duplicates?") must be **fast, free, and identical every run** — and must work with no API key.
- **How it interacts.** Called by `coverage`, `redundancy`, and `intake` nodes, and by
  `tools/vector_store.py`.
- **Typical execution path.** `coverage_node → similarity.match_tests_to_criteria → semantic_sim →
  embeddings` (real vectors if enabled, else a deterministic hashing/lexical fallback).
- **Key files.** `embeddings.py`, `similarity.py`, `clustering.py`, `extraction.py`.
- **Key functions.** `match_tests_to_criteria()`, `find_gaps()`, `cluster_duplicates()`,
  `extract_entities()`.
- **Demo/interview questions:**
  - *NLP vs LLM — where's the line?* NLP does deterministic structure; the LLM only does
    judgement (score rationale, drafting test code).
  - *Why does it work offline?* Every NLP function has a deterministic fallback.

---

## `src/hitl/` — the three human checkpoints

- **Purpose.** The three `interrupt()` points where the graph pauses for human sign-off:
  approve removals, approve ranking, approve generated tests.
- **Why it was created.** This is the safety boundary that makes the agent *recommend, never
  delete*. Nothing destructive happens without an approval written into state.
- **How it interacts.** Wired as three graph nodes; `is_protected` is also used by the
  prioritisation/revise nodes so pinned tests are never even proposed for removal.
- **Typical execution path.** `node → interrupt(payload)` (pause) → caller collects a decision →
  `Command(resume={"__hitl__": decision})` → node writes `approved_*` and continues.
- **Key files.** `interrupts.py`.
- **Key functions.** `hitl_removals_node`, `hitl_priority_node`, `hitl_generated_node`,
  `is_protected()`, `_decision()` (unwraps the resume envelope).
- **Demo/interview questions:**
  - *What's "risk-area pinning"?* Tests matching declared risk areas (e.g. "payment") are locked —
    shown but never in the recommended removal set, and re-filtered out even if submitted.
  - *Can it run unattended?* Yes — `automated` mode auto-approves the reversible recommended set
    (used by the API and the tests).

---

## `src/memory/` — long-term memory

- **Purpose.** A per-project JSON store of prior decisions (never re-suggest a reject), pinned
  "protected" tests, and confirmed "known-flaky" tests.
- **Why it was created.** State lives for one run; some facts must survive between runs. This is
  the feedback loop that makes the agent improve over time.
- **How it interacts.** Read by `retrieval` and `hitl` (pinning); written by `report` at the end
  of each run.
- **Typical execution path.** `retrieval` loads prior decisions/protected → run proceeds →
  `report` saves this run's decisions + confirmed flaky tests.
- **Key files.** `store.py`.
- **Key functions.** `save_decision()`, `get_prior_decisions()`, `record_flaky()`,
  `get_protected_tests()`.
- **Demo/interview questions:**
  - *Does it learn?* Yes — rejected suggestions and pinned tests persist and shape future runs.
  - *Where is it stored?* `.agent_memory/{project}.json` (gitignored). Tests redirect it to a temp
    dir so runs stay isolated.

---

## `prompts/` — what we tell the LLM

- **Purpose.** Versioned Markdown templates for the three LLM tasks: scoring, gap generation, and
  (reserved) prioritisation.
- **Why it was created.** Keeping prompts as files makes them reviewable and diffable, and enforces
  the rule that only these steps call the model.
- **How it interacts.** Loaded by `src/llm.py:load_prompt()`, called from `scoring` and `gap_gen`.
- **Key files.** `scoring_prompt.md` (strict-JSON 6-dimension scores), `gap_generation_prompt.md`
  (one runnable test per gap), `prioritisation_prompt.md` (reserved — tiering is deterministic
  today).
- **Demo/interview questions:**
  - *How do you stop the model from inventing scores?* The prompt requires `null` / "insufficient
    evidence" when data is missing, and we parse defensively.
  - *Is prioritisation LLM-driven?* Not currently — the prompt exists but tiering is deterministic
    (`_tier_for`). Flagged honestly so nobody is surprised.

---

## `sample_data/` — the synthetic fixture + golden answer key

- **Purpose.** A self-contained, realistic dataset the agent analyses in demos and tests.
- **Why it was created.** So the whole pipeline can be demonstrated and regression-tested with no
  external systems (no real Jira/CI/repo needed).
- **How it interacts.** `tools/` reads the fixtures at runtime; `tests/` compares results to the
  golden file.
- **Which files are *read at runtime* by the agent:**
  - `sample_suite/*.py` — the 23-test suite the agent analyses (via `intake`).
  - `sample_criteria.json` — acceptance criteria AC-1..AC-7 (via `coverage`/`retrieval`).
  - `mock_ci_history.json` — per-test runs/fails/avg_seconds (via `redundancy`).
- **Which files are *only test fixtures* (not read at runtime):**
  - `expected_findings.json` — the **golden answer key**; read *only* by `tests/test_graph_e2e.py`,
    never by the agent.
  - `generate_sample_data.py` — the generator/single-source-of-truth; run by a developer to
    (re)create the suite + JSON + golden set, not part of a run.
  - `README.md` — explainer.
- **Demo/interview questions:**
  - *Is the demo data real?* No — it's synthetic, with **planted** duplicates, flaky/slow tests,
    and gaps, so we can prove the agent finds exactly what we expect.
  - *How do you change it?* Edit the constants in `generate_sample_data.py` and re-run it —
    everything else (suite, fixtures, golden set) is derived and stays in sync.

---

## `tests/` — the automated safety net

- **Purpose.** Lock down the non-negotiable safety invariants and prove the pipeline reproduces
  the golden findings.
- **Why it was created.** The safety controls are guaranteed by tests, not prose — "if a safety
  test is in your way, the change is wrong, not the test."
- **What is validated here:**
  - `test_state.py` — the state schema has the right fields/types and append-only reducers.
  - `test_coverage_gate.py` — **Blocker #2**: a floor-breaching removal set routes to `revise`, and
    risk-area tests are never removed.
  - `test_validation_loop.py` — **Blocker #1**: an always-failing validation stops after
    `MAX_GEN_RETRIES` and drops-and-flags (never loops forever).
  - `test_graph_e2e.py` — a full run on `sample_data/` auto-answers the 3 interrupts and asserts
    the four deliverables match `expected_findings.json`.
- **How it interacts.** Imports `src/` directly and runs `build_graph().invoke(...)` in
  `automated` mode; `conftest.py` isolates the memory store per test.
- **Key functions.** the e2e `outputs` fixture; the unit checks on `coverage_floor_gate` and
  `route_after_validation`.
- **Demo/interview questions:**
  - *How do you know it's safe?* Two dedicated tests prove the two loops terminate and the floor
    gate blocks unsafe removals; the e2e test proves end-to-end correctness against a golden set.
  - *How do you run them?* `pytest` (all) or `pytest tests/test_graph_e2e.py -v` (one).

---

## `frontend/` — the React demo UI

- **Purpose.** A single-page React app to run the agent and review results visually. Contains no
  analysis logic.
- **Why it was created.** To make the checkpoints and deliverables tangible for a non-technical
  audience — the human-approval story is much clearer as clickable cards.
- **How the frontend talks to the backend.** Over HTTP to `api.py` (`http://127.0.0.1:8000`), via
  `src/api.ts`:
  - `POST /runs` — start a run (returns the first checkpoint or the final outputs).
  - `POST /runs/{id}/resume` — submit a checkpoint decision.
  - `GET /runs/{id}` — poll the live progress feed (every ~2s).
  - `GET /health` — liveness.
  `api.ts` normalises backend field names into clean types; `App.tsx` is a state machine
  (`input → running → hitl → results`).
- **Typical execution path.** Fill the form → `POST /runs` → render approval card → approve →
  `POST /resume` (×3) → render the 4 result tabs.
- **Key files.** `App.tsx` (state machine), `api.ts` (HTTP), `types.ts` (contract), the 3 HITL
  cards, the 4 result tabs.
- **Demo/interview questions:**
  - *Where's the logic?* All in the Python backend; the UI only captures input, shows progress,
    and displays results.
  - *How does the approval pause work over HTTP?* Each `POST` blocks to the next checkpoint;
    approvals are wrapped as `{"__hitl__": …}` so even an empty "keep all" resumes correctly.
  - *Note:* the frontend already ships with its own detailed `frontend/README.md`.

---

## `learning/` — LangGraph tutorials (onboarding)

- **Purpose.** Three tiny standalone scripts that teach the LangGraph mechanics the agent relies
  on: state+nodes, conditional branching/loops, and interrupt/resume.
- **Why it was created.** New contributors learn each concept in isolation before meeting them
  combined in `src/graph.py`. Nothing in `src/` imports these.
- **Key files.** `01_counter_graph.py` (linear spine), `02_conditional_branch.py` (the loop
  pattern), `03_interrupt_resume.py` (the HITL pattern).
- **Demo/interview questions:**
  - *How would a new engineer ramp up?* Run these three files top to bottom — they mirror the real
    graph's spine, loops, and interrupts.

---

## `logs/` and `outputs/` — runtime artifacts

- **`logs/` — the trace.** Purpose: a rotating human-readable log (`agent.log`) written by
  `observability.audit()` alongside the in-state `audit_log`. Format:
  `timestamp LEVEL test_optimiser.<node> | <event> | <details>`. Used to debug a run after the
  fact. (Gitignored; created at runtime.)
- **`outputs/` — the deliverables.** Purpose: the four JSON files each run produces —
  `scorecard.json`, `coverage_gap_map.json`, `redundancy_flakiness_report.json`,
  `optimised_plan.json`. Written by `main.write_outputs()`; the same objects are returned by the
  API and rendered by the frontend tabs. (Gitignored; overwritten each run.)
- **Demo/interview questions:**
  - *How do I see what happened?* Read `logs/agent.log`, or the `audit_log` in the API response.
  - *What are the four deliverables?* Health scorecard, coverage & gap map, redundancy/flakiness
    report, and the optimised plan (current vs proposed).

---

## `docs/` — documentation

- **Purpose.** The written knowledge base: the canonical spec, setup/config/output references, the
  annotated file map, the architecture/flow deep-dives, and this walkthrough.
- **Key files.** `AGENT_SPEC.md` (design authority), `INSTALL.md`, `CONFIGURATION.md`,
  `OUTPUTS.md`, `STRUCTURE.md` (this file), and the four flow docs (`ARCHITECTURE_DETAILED`,
  `EXECUTION_FLOW`, `DATA_FLOW`, `STATE_FLOW`, `FUNCTION_CALL_MAP`).
- **Demo/interview questions:**
  - *What's the source of truth for design?* `AGENT_SPEC.md` — the code follows the spec.

---

## Manager's cheat-sheet (the story in five beats)

1. **Problem.** Test suites grow slow, flaky, and redundant, yet teams fear cutting tests because
   they might lose coverage.
2. **Solution.** An agent that analyses the suite and proposes a leaner, re-prioritised plan
   *without ever dropping below the coverage floor* — and never acts without human approval.
3. **Trust.** Three approval checkpoints, risk-area pinning, sandbox-only test checks, and "no
   faked data" — all enforced by automated safety tests.
4. **Resilience.** Every external call degrades gracefully; the whole thing runs offline with no
   API key, and uses Gemini for judgement when available.
5. **Proof.** A synthetic fixture with planted findings plus a golden-set end-to-end test show the
   agent finds exactly the duplicates, flaky/slow tests, and gaps we expect.

**Most likely live-demo question — "show me it's safe":** point to `tests/test_coverage_gate.py`
and `tests/test_validation_loop.py` (the two loops provably terminate and the floor gate blocks
unsafe removals), then run `pytest` and the CLI on `sample_data/sample_suite`.
