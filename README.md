# Test Optimiser Agent

An L3 goal-driven LangGraph agent that analyses an existing test suite and
produces an optimised, re-prioritised test plan — pausing for human approval
at three checkpoints.

## What lives where
- `src/state.py`     — the shared state object passed between every node
- `src/graph.py`     — wires nodes + edges + routing + checkpointer into the graph
- `src/config.py`    — all thresholds and constants in one place
- `src/nodes/`       — the 10 work nodes (one file each)
- `src/nlp/`         — embeddings, similarity, clustering, text extraction
- `src/tools/`       — external integrations + the retry/degrade wrapper
- `src/hitl/`        — human-in-the-loop interrupt payloads & handlers
- `src/memory/`      — long-term per-project store
- `prompts/`         — LLM prompt templates (scoring, prioritisation, generation)
- `fixtures/`        — a toy suite + mock data to develop against
- `tests/`           — unit + end-to-end tests (gate, loop bound, full run)
- `learning/`        — 3 tiny standalone LangGraph examples to learn the mechanics

## Quick start
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your API key
4. Learn the mechanics: run the `learning/` scripts in order
5. Run the agent: `python main.py --suite fixtures/sample_suite`
