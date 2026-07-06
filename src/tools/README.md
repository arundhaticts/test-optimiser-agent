# `src/tools/` — External integrations (via the retry/degrade wrapper)

## 1. Purpose

Every point where the agent touches the outside world — reading the repo, parsing tests,
loading coverage/CI/criteria, the vector store, and the sandbox — lives here. All of it is
funnelled through **`call_tool()`**, which turns any failure into a uniform envelope so a single
flaky dependency never crashes the graph (spec Blocker #3).

## 2. Why this folder exists

Nodes must stay pure and deterministic. Isolating I/O and side effects behind one wrapper means
retries, degradation, and error surfacing are implemented **once**, and nodes simply record a
`tool_error` and carry on with a fallback instead of throwing.

## 3. How it fits into the overall architecture

```
   src/nodes/*                      src/llm.py
       │  call_tool(fn, …)              │ (also invoked via call_tool)
       ▼                                ▼
 ┌──────────────── src/tools/ ─────────────────────────────┐
 │ tool_wrapper.call_tool → {"ok":…, "data"/"error", fatal} │
 │   ├ repo_reader   → test_parser (AST)                     │
 │   ├ coverage_parser (stub / fallback estimate)            │
 │   ├ ci_history      → sample_data/mock_ci_history.json    │
 │   ├ test_management → sample_data/sample_criteria.json    │
 │   ├ vector_store    → src/nlp/embeddings                  │
 │   └ sandbox         → subprocess syntax check             │
 └──────────────────────────────────────────────────────────┘
```

## 4. Files inside the folder

`__init__.py`, `tool_wrapper.py`, `repo_reader.py`, `test_parser.py`, `coverage_parser.py`,
`ci_history.py`, `test_management.py`, `vector_store.py`, `sandbox.py`.

## 5. Responsibilities of each file

- **`tool_wrapper.py`** — the contract for all external calls.
  - `call_tool(fn, *args, retries=TOOL_RETRIES, backoff=BACKOFF_BASE, **kwargs) -> dict`
    returns `{"ok": True, "data": …}` or `{"ok": False, "error": str, "fatal": bool}`. Never
    raises for `TransientError`/`FatalError`. `FatalError` → immediate degrade (no retry);
    `TransientError`/unexpected → retry with exponential backoff `backoff ** attempt`.
  - `tool_error_entry(tool, error, degrade) -> dict` → the shape appended to `state["tool_errors"]`.
  - Exception classes **`TransientError`** (retry) and **`FatalError`** (don't retry).
- **`repo_reader.py`** — `read_tests(path)` (→ `test_parser.parse`, raises `FatalError` if
  unreadable), `read_source(path)`, `detect_conventions(tests) -> dict` (framework/naming/docstrings).
- **`test_parser.py`** — `parse(path)` dispatches per framework; `_parse_pytest` extracts
  `def test_*` via **AST only (never executes)**; junit/jest/cypress are `NotImplementedError` stubs.
- **`coverage_parser.py`** — placeholder for `parse_coverage(path)` + static call-graph fallback
  (documented, not yet implemented).
- **`ci_history.py`** — `get_history(test_id)`, `all_history()`, `_load()` read
  `sample_data/mock_ci_history.json`; missing history returns `None`/`{}` (non-fatal).
- **`test_management.py`** — `get_acceptance_criteria(project_id=None)` reads
  `sample_data/sample_criteria.json` (`"criteria"` key); `get_known_issues()` stub. Stands in for Jira/Xray.
- **`vector_store.py`** — in-memory `VectorStore` with `upsert(id, text, metadata)` and
  `query(text, k=5)` (cosine over `src.nlp.embeddings`); module-level singleton wrappers.
- **`sandbox.py`** — `validate(test_code, timeout=10.0)` compiles code in a **subprocess**
  (syntax/import check only, never runs bodies); returns `{"valid": bool, "error": str}`.

## 6. Inputs

File paths, test IDs, project IDs, text to embed/query, generated test code; the two fixed
`sample_data/*.json` paths; `config.TOOL_RETRIES`/`BACKOFF_BASE`.

## 7. Outputs

The `call_tool` envelope; parsed test dicts; conventions dict; criteria list; CI stats
`{runs, fails, avg_seconds}`; vector hits `[{id, text, metadata, score}]`; sandbox verdict.

## 8. Dependencies

`src.config`, `src.observability`, `src.nlp.embeddings` (vector store); stdlib `ast`,
`subprocess`, `json`, `pathlib`, `time`. No third-party network SDKs in the prototype path.

## 9. Which folders call/use it

`src/nodes/` (intake, coverage, redundancy, retrieval, scoring, gap_generation, validation) and
`src/llm.py` (Gemini calls flow through `call_tool`).

## 10. Which folders it calls/uses

`sample_data/` (CI history + criteria fixtures), `src/nlp/` (embeddings for the vector store).

## 11. Runtime execution flow

```
node → call_tool(fn, …)
         try fn():
           TransientError / Exception → sleep(backoff**attempt), retry ≤ retries
           FatalError                 → return {ok:False, fatal:True} immediately
           success                    → return {ok:True, data:…}
node checks env["ok"]:
   ok    → use env["data"]
   not ok→ append tool_error_entry(...) to tool_errors, continue with deterministic fallback
```

## 12. Common debugging locations

- **Everything degrades** → `call_tool` retry/backoff and whether `fn` raises `Fatal` vs `Transient`.
- **No criteria / no CI history** → the two fixed `sample_data/*.json` paths in `test_management`/`ci_history`.
- **Generated test wrongly rejected** → `sandbox.validate` (timeout, `ERR:` parsing, subprocess stderr).
- **Empty retrieval** → `vector_store` (nothing upserted) or `nlp.embeddings` offline behaviour.
- **Parser misses tests** → `test_parser._parse_pytest` AST logic / `unparseable` markers.
