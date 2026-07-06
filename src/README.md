# `src/` — Agent logic

## 1. Purpose

`src/` is the **whole agent**: the shared state schema, the compiled LangGraph, the single
LLM client, centralised config, observability, and the sub-packages that do the work
(`nodes/`, `tools/`, `nlp/`, `hitl/`, `memory/`). Everything the agent *thinks and does*
lives here; the repo root only launches it.

## 2. Why this folder exists

To keep **orchestration logic** separate from **entrypoints** (`main.py`/`api.py`) and from
**data/config artifacts** (`prompts/`, `sample_data/`, `outputs/`). One importable package
(`src`) can be driven by the CLI, the API, or the test suite without change.

## 3. How it fits into the overall architecture

```
 main.py / api.py
        │  build_graph()
        ▼
 ┌──────────────── src/ ────────────────────────────────────────┐
 │  graph.py   ── wires nodes + edges + 2 loops + 3 interrupts   │
 │  state.py   ── TestOptimiserState (the shared "clipboard")    │
 │  config.py  ── thresholds, model names, feature flags         │
 │  llm.py     ── single Gemini client (offline-safe)            │
 │  observability.py ── logging + append-only audit_log          │
 │                                                               │
 │  nodes/  → the 10 work nodes (+ revise, drop_failing, model)  │
 │  tools/  → external I/O via call_tool() retry/degrade wrapper │
 │  nlp/    → deterministic text backbone (offline fallback)     │
 │  hitl/   → the 3 human-in-the-loop interrupts                 │
 │  memory/ → long-term per-project JSON store                   │
 └───────────────────────────────────────────────────────────────┘
```

The **state object flows down**, each node returns only the keys it changes, and LangGraph
merges them. Cross-cutting modules (`config`, `llm`, `observability`) are imported almost
everywhere.

## 4. Files inside the folder (top level)

| File | Role |
|------|------|
| `__init__.py` | package marker (`"Test Optimiser Agent package."`) |
| `state.py` | `TestOptimiserState` TypedDict — the data shape every node reads/writes |
| `config.py` | every threshold, model name, feature flag; loads `.env`, injects truststore |
| `graph.py` | registers nodes/edges/routing, `make_checkpointer()`, `build_graph()` |
| `llm.py` | the single Gemini client: `complete`, `llm_available`, `extract_json`, `load_prompt` |
| `observability.py` | `configure_logging`, `get_logger`, `audit` (structured append-only trail) |

Sub-packages: `nodes/`, `tools/`, `nlp/`, `hitl/`, `memory/` (each has its own README).

## 5. Responsibilities of each file

- **`state.py`** — a single `TypedDict(total=False)` with inputs, working state, human
  decisions, loop/error control, results, and observability. `tool_errors` and `audit_log`
  are `Annotated[list, add]` (append-only reducers).
- **`config.py`** — the *only* place numbers live: `MAX_GEN_RETRIES=3`, `MAX_REVISE_ITERS=10`,
  `DEFAULT_COVERAGE_TARGET=0.80`, similarity thresholds (`CRITERIA_MATCH_THRESHOLD`,
  `DUPLICATE_THRESHOLD`, `GAP_THRESHOLD`), `FLAKY_FAIL_RATE`, `SLOW_TEST_SECONDS`, the coverage
  model constants, `TOOL_RETRIES`/`BACKOFF_BASE`, model names, and `OFFLINE_MODE`. Loads
  `.env` and injects corporate TLS truststore on import.
- **`graph.py`** — declares 10 work nodes + `revise` + `drop_failing` + 3 HITL nodes, wires the
  linear spine, the coverage-floor gate loop (`coverage_floor_gate`), and the validation loop
  (`route_after_validation`); `make_checkpointer()` picks MemorySaver or SqliteSaver.
- **`llm.py`** — wraps `google-genai`; classifies failures as `FatalError` (auth/config, no
  retry) vs `TransientError` (retryable); `extract_json` parses fenced/raw JSON; offline-safe.
- **`observability.py`** — rotating `logs/agent.log` + console; `audit(node, event, **details)`
  returns a dict for `audit_log` *and* logs it.

## 6. Inputs

Initial state (from `main.py`/`api.py`), `.env`/environment, prompt templates, and fixture data.

## 7. Outputs

A final state whose `final_outputs` holds the four deliverables; log lines; audit entries.

## 8. Dependencies

`langgraph`, `langgraph.checkpoint.*`, `google-genai` (via `llm.py`), plus stdlib. Sub-packages
add optional `sentence-transformers`, `spacy`, `chromadb`.

## 9. Which folders call/use it

`main.py`, `api.py`, and `tests/` import `src.graph.build_graph` and `src.state`.

## 10. Which folders it calls/uses

`prompts/` (templates via `llm.load_prompt`), `sample_data/` (via `tools/`), `logs/` and
`outputs/` (via observability / entrypoints), and the `.agent_memory/` store (via `memory/`).

## 11. Runtime execution flow

```
build_graph() → StateGraph(TestOptimiserState) compiled with a checkpointer
invoke(initial_state):
  intake → coverage → redundancy → retrieval → scoring
    → hitl_removals  (interrupt 1)
    → prioritisation → coverage_floor_gate ⇄ revise → hitl_priority (interrupt 2)
    → gap_gen → validation ⇄ (retry ≤3) → drop_failing → hitl_generated (interrupt 3)
    → assemble → report → END
```

## 12. Common debugging locations

- **State field missing/wrong type** → `state.py` (and `tests/test_state.py`).
- **A threshold behaves oddly** → `config.py` (never hard-coded elsewhere).
- **Graph shape / routing** → `graph.py` edges and the two conditional-edge blocks.
- **LLM silently disabled** → `llm.llm_available()` and `config.OFFLINE_MODE`.
- **Missing/duplicate audit lines** → `observability.audit` and append-only reducers.
