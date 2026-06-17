# Test Optimiser Agent

An L3, goal-driven LangGraph agent that analyses an existing test suite and produces an
optimised, re-prioritised test plan — scoring suite health, mapping coverage against
acceptance criteria, flagging redundant/flaky/slow tests, and drafting tests for real gaps —
while pausing for human approval at three checkpoints. It **recommends, never deletes**.
LLM judgement is powered by **Google Gemini (`gemini-2.5-flash`)**; it also runs fully
**offline** with deterministic fallbacks (no API key required).

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # add GEMINI_API_KEY (optional — runs offline without it)
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

## Project structure

```
test-optimiser-agent/
├── README.md                  ← you are here (entry point)
├── main.py                    ← thin CLI entrypoint
├── api.py                     ← thin FastAPI bridge (HTTP ↔ graph)
├── requirements.txt
├── .env.example
├── docs/                      ← all project documentation
│   ├── AGENT_SPEC.md
│   ├── CLAUDE.md
│   ├── PROJECT_HANDOFF.md
│   ├── INSTALL.md
│   ├── CONFIGURATION.md
│   └── OUTPUTS.md
├── src/
│   ├── state.py               ← TestOptimiserState (shared state object)
│   ├── config.py              ← all thresholds, models, feature flags
│   ├── llm.py                 ← Gemini client (offline-safe)
│   ├── observability.py       ← logging + append-only audit trail
│   ├── graph.py               ← nodes + edges + routing + checkpointer
│   ├── nodes/                 ← the 10 work nodes (+ revise, drop_failing, _coverage_model)
│   ├── nlp/                   ← embeddings, similarity, clustering, extraction
│   ├── tools/                 ← external integrations + retry/degrade wrapper
│   ├── hitl/                  ← the 3 human-in-the-loop interrupt checkpoints
│   └── memory/                ← long-term per-project store
├── prompts/                   ← LLM prompt templates (scoring, prioritisation, generation)
├── sample_data/               ← generator + synthetic suite/CI/criteria + golden eval set
├── learning/                  ← 3 standalone LangGraph examples (learn the mechanics)
├── tests/                     ← unit + e2e (coverage-gate, validation-loop, golden-set)
├── logs/                      ← rotating agent.log
└── outputs/                   ← the four written deliverables
```
