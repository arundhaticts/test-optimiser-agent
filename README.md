# Test Optimiser Agent

An L3, goal-driven LangGraph agent that analyses an existing test suite and produces an
optimised, re-prioritised test plan — scoring suite health, mapping coverage against
acceptance criteria, flagging redundant/flaky/slow tests, and drafting tests for real gaps —
while pausing for human approval at three checkpoints. It **recommends, never deletes**.
LLM judgement is powered by **Google Gemini (`gemini-2.5-flash`)**; it also runs fully
**offline** with deterministic fallbacks (no API key required).

> This file is both the **project entry point** and the **root-folder README**. The first
> two sections get you running; the rest ("Root folder as an architectural unit") documents
> the repository the way every sub-folder README does — purpose, fit, files, I/O,
> dependencies, runtime flow, and debugging.

## Quick start

```bash
pip install -r requirements.txt
# create a .env with GEMINI_API_KEY (optional — runs offline without it)
echo "GEMINI_API_KEY=your-key-here" > .env
python main.py --suite sample_data/sample_suite --goal speed
```

See **[docs/INSTALL.md](docs/INSTALL.md)** for the full, copy-paste setup (prerequisites,
virtualenv, env vars, sample data, first run, and common-error fixes).

## Documentation

| Document | What it covers |
|----------|----------------|
| [docs/AGENT_SPEC.md](docs/AGENT_SPEC.md) | Full design, architecture, ADLC phases, Mermaid diagram, node specs, safety controls |
| [docs/CLAUDE.md](docs/CLAUDE.md) | Guide for AI coding assistants — rules, conventions, file map |
| [docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md) | Phase-by-phase build state and how to resume |
| [docs/INSTALL.md](docs/INSTALL.md) | Full installation guide |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every config knob explained + tuning guide |
| [docs/OUTPUTS.md](docs/OUTPUTS.md) | Output format reference for the four deliverables |
| [docs/STRUCTURE.md](docs/STRUCTURE.md) | Annotated file map — every file, one line each |

**Per-folder READMEs** (this documentation set): [frontend/](frontend/README.md) ·
[prompts/](prompts/README.md) · [src/](src/README.md) · [src/nodes/](src/nodes/README.md) ·
[src/tools/](src/tools/README.md) · [src/nlp/](src/nlp/README.md) ·
[src/memory/](src/memory/README.md) · [src/hitl/](src/hitl/README.md) ·
[tests/](tests/README.md) · [learning/](learning/README.md) · [logs/](logs/README.md) ·
[outputs/](outputs/README.md)

---

# Root folder as an architectural unit

## 1. Purpose

The repository root is the **composition layer**: it holds the two entrypoints that wire the
agent to the outside world (`main.py` for the CLI, `api.py` for HTTP), the dependency and
test-runner manifests, and the top-level directories that each own one concern. Nothing here
contains analysis logic — the logic lives in `src/`; the root just *assembles and launches* it.

## 2. Why this folder exists

Every project needs a single front door. The root separates **how you invoke the agent**
(CLI args, HTTP requests) from **what the agent does** (`src/`), so the same compiled graph can
be driven from a terminal, a web UI, or a test harness without duplicating logic.

## 3. How it fits into the overall architecture

```
                        ┌──────────────────────────────────────────┐
   CLI  ──> main.py ──▶ │                                          │
                        │   build_graph()  (src/graph.py)           │
 HTTP ──> api.py  ──▶   │   the compiled LangGraph state machine    │──▶ outputs/  (4 JSON files)
   ▲                    │                                          │──▶ logs/agent.log
   │                    └──────────────────────────────────────────┘
 frontend/ (React)                     │ reads/writes
                                       ▼
                   src/ (state · nodes · tools · nlp · hitl · memory · llm)
                   prompts/  sample_data/  (inputs)
```

`main.py` and `api.py` are thin shells over the *same* `build_graph()`. The graph pulls inputs
from `sample_data/` and `prompts/`, streams progress to `logs/`, and writes deliverables to
`outputs/`. The `frontend/` talks only to `api.py`.

## 4. Files inside the folder (root-level)

| File | Role |
|------|------|
| `main.py` | CLI entrypoint |
| `api.py` | FastAPI HTTP bridge |
| `requirements.txt` | Python dependency manifest |
| `pytest.ini` | pytest discovery/config |
| `README.md` | this file |
| `.env` | local secrets/flags (gitignored) |
| `.gitignore` | excludes venv, caches, logs, outputs, memory, vector DB |

Top-level directories: `src/`, `frontend/`, `prompts/`, `sample_data/`, `tests/`,
`learning/`, `docs/`, `logs/`, `outputs/`.

## 5. Responsibilities of each file

- **`main.py`** — `initial_state(args)` builds the starting state from CLI args;
  `run(args)` invokes the graph and, on each `__interrupt__`, calls `_answer_interrupt(payload)`
  to read a decision from stdin and resumes via `Command(resume=…)`; `write_outputs(outputs, dir)`
  writes the four JSON deliverables; `main()` wires argparse (`--suite`, `--project`, `--goal`,
  `--coverage-target`, `--risk-areas`, `--run-mode`).
- **`api.py`** — one compiled `GRAPH`; `POST /runs` starts a run and **blocks to the next
  checkpoint**, `POST /runs/{id}/resume` submits a decision (wrapped as `{"__hitl__": …}`),
  `GET /runs/{id}` returns audit/status, `GET /health` reports liveness. CORS is open to the
  Vite dev origins. `_package()` shapes each response as `awaiting_approval` or `completed`.
- **`requirements.txt`** — langgraph, google-genai, fastapi/uvicorn, pydantic, python-dotenv,
  pytest, plus optional sentence-transformers/spacy/chromadb/langgraph-checkpoint-sqlite.
- **`pytest.ini`** — `pythonpath = .` (so `import src.*` works), `testpaths = tests`, and a
  collection filter so the `TestOptimiserState` TypedDict is not mistaken for a test class.

## 6. Inputs

- CLI args (`main.py`) or JSON request bodies (`api.py`).
- Environment via `.env` (`GEMINI_API_KEY`, feature flags, `CHECKPOINT_DB`).
- Fixture data under `sample_data/` (suite, CI history, criteria) and templates under `prompts/`.

## 7. Outputs

- Four JSON deliverables in `outputs/` (`scorecard.json`, `coverage_gap_map.json`,
  `redundancy_flakiness_report.json`, `optimised_plan.json`).
- Rotating `logs/agent.log`.
- HTTP JSON responses (`api.py`), console summary (`main.py`).

## 8. Dependencies

`langgraph` (orchestration), `google-genai` (Gemini), `fastapi`/`uvicorn` (HTTP),
`pydantic` (request models), `python-dotenv`, and the whole `src/` package.

## 9. Which folders call/use it

- `frontend/` calls `api.py` over HTTP.
- Operators/CI call `main.py` and `tests/`.

## 10. Which folders it calls/uses

`src/` (via `build_graph`), which in turn reaches `prompts/`, `sample_data/`, `logs/`,
`outputs/`, and the long-term memory store.

## 11. Runtime execution flow

```
CLI:   main.py → initial_state → graph.invoke → [interrupt → stdin → resume]×3 → write_outputs → print summary
HTTP:  POST /runs → graph.invoke (blocks to checkpoint) → awaiting_approval
       POST /runs/{id}/resume → graph.invoke (Command(resume)) → next checkpoint … → completed(outputs)
```

## 12. Common debugging locations

- **Run won't start / import errors** → `pytest.ini` pythonpath, virtualenv, `requirements.txt`.
- **No LLM / everything "degraded"** → `.env` `GEMINI_API_KEY`, `src/config.py` `OFFLINE_MODE`.
- **HITL never resumes over HTTP** → the `{"__hitl__": …}` envelope in `api.py` / `src/hitl/interrupts.py`.
- **Outputs missing** → `write_outputs()` in `main.py`; `report_node` in `src/nodes/report.py`.
- **Trace what happened** → `logs/agent.log` and the `audit_log` in each response.

## Project structure

```
test-optimiser-agent/
├── README.md                  ← you are here (entry point + root README)
├── main.py                    ← thin CLI entrypoint
├── api.py                     ← thin FastAPI bridge (HTTP ↔ graph)
├── requirements.txt
├── pytest.ini
├── .env                       ← your local config/secrets (gitignored)
├── docs/                      ← all project documentation
├── src/                       ← all agent logic (state, graph, nodes, tools, nlp, hitl, memory)
├── prompts/                   ← LLM prompt templates (scoring, prioritisation, generation)
├── sample_data/               ← generator + synthetic suite/CI/criteria + golden eval set
├── learning/                  ← 3 standalone LangGraph examples (learn the mechanics)
├── tests/                     ← unit + e2e (coverage-gate, validation-loop, golden-set)
├── frontend/                  ← React demo UI (Vite + TypeScript)
├── logs/                      ← rotating agent.log
└── outputs/                   ← the four written deliverables
```
