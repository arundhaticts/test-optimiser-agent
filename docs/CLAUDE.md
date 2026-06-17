# CLAUDE.md — Guide for AI Coding Assistants

A working guide for Claude Code (or any AI coding assistant) contributing to this repo.
Read this, then [AGENT_SPEC.md](AGENT_SPEC.md) (the canonical design authority) and
[PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) (phase-by-phase build state).

> **Provider note:** LLM judgement is powered by **Google Gemini (`gemini-2.5-flash`)**. The
> code reads `GEMINI_API_KEY` and talks to Gemini via `src/llm.py` (the `google-genai` SDK).
> `AGENT_SPEC.md` is the source of truth for architecture and behaviour; the code is the
> source of truth for the provider.

---

## 1. Project overview

An **L3, goal-driven LangGraph agent** that takes an existing test suite and makes it
leaner, faster, and more reliable **without losing coverage**. You give it a goal
("get this suite under 10 minutes without dropping below 80% coverage"); it scores the
suite, maps coverage against code and acceptance criteria, flags redundant/flaky/slow/
obsolete tests, re-prioritises into smoke/regression/full tiers, and drafts tests for
real gaps. It **recommends, never deletes** — it pauses for human sign-off at three
checkpoints.

**Stack:** LangGraph (orchestration) · Google Gemini `gemini-2.5-flash` via `google-genai`
(judgement: scoring rationale, gap-test drafting) · sentence-transformers (semantic
embeddings, optional) · spaCy (NER, optional) · Chroma (vector store, optional) ·
deterministic NLP/scoring fallbacks so the graph runs **offline by default** with no key.

---

## 2. Architecture summary

A single typed **state object** ([../src/state.py](../src/state.py)) flows through a graph
of **10 work nodes + 2 auxiliary nodes**. The analysis spine is linear:

```
intake → coverage → redundancy → retrieval → scoring
  → HITL 1 (approve removals)
  → prioritisation → [coverage-floor gate] ⇄ revise → HITL 2 (approve ranking)
  → gap_generation → validation ⇄ (retry ≤3) → drop_failing → HITL 3 (approve tests)
  → assemble → report → END
```

- **intake** normalises the suite; **coverage** maps tests↔criteria and finds gaps;
  **redundancy** flags duplicates/flaky/slow; **retrieval** pulls prior-run memory;
  **scoring** rates six health dimensions (LLM, with deterministic fallback).
- **prioritisation** re-tiers the surviving suite; the **coverage-floor gate** is a real
  routing node that blocks any change set projected below target and loops through
  **revise**; **gap_generation** drafts tests (LLM); **validation** syntax/import-checks
  them in the sandbox, looping up to `MAX_GEN_RETRIES`, then **drop_failing**.
- **assemble** builds the side-by-side optimised plan; **report** renders the four
  deliverables and writes outcomes to memory.

See [AGENT_SPEC.md](AGENT_SPEC.md) for the full Mermaid diagram and per-node detail.

**The three HITL checkpoints** (`src/hitl/interrupts.py`), each an `interrupt()` that
pauses the graph until a human decision is written into state:

| # | Checkpoint | Gates |
|---|-----------|-------|
| 1 | `approve_removals` | which flaky/duplicate tests may be quarantined/merged/removed |
| 2 | `approve_ranking` | the smoke/regression/full tiering before tests are generated |
| 3 | `approve_tests` | which generated gap tests are accepted into the plan |

---

## 3. Key rules — never break these

These are the spec's Safety Controls; tests in [../tests/](../tests/) catch regressions.

- **`MAX_GEN_RETRIES = 3`** — the validation→gap_gen loop cap. **Never remove or raise it
  without updating the safety test.** The run must always terminate.
- **The coverage-floor gate is a real node, not prose** (`coverage_floor_gate` in
  `src/nodes/prioritisation.py`). It must be able to *block* a floor-breaching change set
  and route to `revise`. **Never bypass it or downgrade it to a warning.**
- **Every external call goes through `src/tools/tool_wrapper.py`** (`call_tool(fn, …)`).
  **Never** call a tool/SDK/file/HTTP dependency directly from a node. LLM calls go through
  `src/llm.py`, which is itself invoked via `call_tool`.
- **Nothing destructive is automatic.** Removals, merges, and commits require a human
  approval written into state at a HITL checkpoint. The agent recommends; it never
  deletes/commits/merges unattended.
- **Generated tests run only in the sandbox** (`src/tools/sandbox.py`) for a syntax/import
  check — **never against production**.
- **Risk-area tests are pinned** (`is_protected`) and never eligible for removal.
- **Append-only observability.** `audit_log` and `tool_errors` use `Annotated[list, add]`
  — append, never overwrite.
- **No faked data.** Missing inputs → "insufficient evidence" / "needs more data", never a
  guessed score.

---

## 4. File map

| Path | What it is |
|------|-----------|
| [../main.py](../main.py) | thin CLI entrypoint; builds the graph, drives interrupts from stdin |
| [../api.py](../api.py) | thin FastAPI bridge (HTTP ↔ graph): `POST /runs`, `/runs/{id}/resume`, `GET /runs/{id}`, `/health` |
| [../src/state.py](../src/state.py) | `TestOptimiserState` TypedDict — the shape every node reads/writes |
| [../src/config.py](../src/config.py) | every threshold + model name + feature flag; loads `.env`, injects `truststore`. **No magic numbers anywhere else.** |
| [../src/llm.py](../src/llm.py) | the single Gemini client (`complete`, `llm_available`, `extract_json`, `load_prompt`); offline-safe |
| [../src/observability.py](../src/observability.py) | logging + structured append-only `audit_log`; rotating `logs/agent.log` |
| [../src/graph.py](../src/graph.py) | registers nodes + edges + routing + checkpointer; mirrors the spec diagram |
| [../src/nodes/](../src/nodes/) | the 10 work nodes (one file each) + `revise` & `coverage_floor_gate` (in `prioritisation.py`) + `route_after_validation` & `drop_failing` (in `validation.py`) + shared `_coverage_model.py` |
| [../src/nlp/](../src/nlp/) | `embeddings`, `similarity`, `clustering`, `extraction` — deterministic backbone with offline fallbacks |
| [../src/tools/](../src/tools/) | `tool_wrapper` + `repo_reader`, `test_parser`, `coverage_parser`, `ci_history`, `test_management`, `vector_store`, `sandbox` |
| [../src/hitl/interrupts.py](../src/hitl/interrupts.py) | the 3 interrupt payload builders & HITL nodes; `is_protected` |
| [../src/memory/store.py](../src/memory/store.py) | long-term per-project store (prior decisions, protected/flaky tests) |
| [../prompts/](../prompts/) | LLM prompt templates: `scoring_prompt.md`, `prioritisation_prompt.md`, `gap_generation_prompt.md` |
| [../sample_data/](../sample_data/) | `generate_sample_data.py` (single source of truth) → `sample_suite/test_sample.py`, `mock_ci_history.json`, `sample_criteria.json`, and the golden `expected_findings.json` |
| [../tests/](../tests/) | `test_state`, `test_coverage_gate` (Blocker #2), `test_validation_loop` (Blocker #1), `test_graph_e2e` (golden-set regression), `conftest` |
| [../learning/](../learning/) | 3 standalone LangGraph examples (counter → conditional branch → interrupt/resume) — learn the mechanics first |
| [../logs/](../logs/), [../outputs/](../outputs/) | rotating run log; the four written deliverables |

---

## 5. Coding conventions

- **Node signature:** `def some_node(state: TestOptimiserState) -> dict:` returning **only
  the state keys it updates** (LangGraph merges them). Routing functions return a **string**
  (the next node's name).
- **All thresholds/constants come from [../src/config.py](../src/config.py).** If you're
  about to type a number meaning "flaky", "slow", "duplicate", "gap", or a retry count, it
  belongs in config.
- **All external calls go through `call_tool` in
  [../src/tools/tool_wrapper.py](../src/tools/tool_wrapper.py).** No bare requests/file reads/
  SDK calls from inside a node. LLM calls go through `src/llm.py`.
- **Append to `audit_log` on every significant action:**
  `return {"audit_log": [audit("<node>", "<event>", **details)]}`. Never `print()` from a
  node — use `get_logger(__name__)`.
- **Type hints everywhere.** Prompts return **strict JSON**; parse defensively and emit the
  "insufficient evidence" sentinel on missing data.
- **NLP vs LLM split:** deterministic NLP ([../src/nlp/](../src/nlp/)) for matching, dedup,
  gap-finding, and log triage; the LLM only for judgement (scoring rationale,
  prioritisation trade-offs, drafting test code).

### Adding a node (checklist)
1. Add any new state fields to [../src/state.py](../src/state.py) first.
2. Implement `node(state) -> dict`; pull thresholds from config, reach dependencies via
   `call_tool`, append to `audit_log`.
3. If it branches, add a routing function returning the next node name.
4. Register it in [../src/graph.py](../src/graph.py) and wire its edges to match the diagram.
5. Cover it in [../tests/](../tests/); if it touches a safety invariant, add an explicit
   assertion and verify against the golden set.

---

## 6. What not to touch

- **`sample_data/` golden files are generated, not hand-edited.** Change the planted
  constants in [../sample_data/generate_sample_data.py](../sample_data/generate_sample_data.py)
  and re-run it — `test_sample.py`, the JSON fixtures, and `expected_findings.json` are all
  derived from those constants and must stay in sync.
- **[AGENT_SPEC.md](AGENT_SPEC.md) is the design authority.** Code follows the spec, not the
  other way around. Don't quietly diverge from it; if reality must differ (e.g. the Gemini
  migration), flag it and update the relevant doc.
- **Don't weaken the safety invariants in section 3** to make a change "work". If a safety
  test is in your way, the change is wrong, not the test.
