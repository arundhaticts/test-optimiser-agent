# `tests/` — Unit & end-to-end safety net

## 1. Purpose

The automated **safety net**. These tests lock down the spec's non-negotiable invariants — the
state schema, the coverage-floor gate (Blocker #2), the bounded validation loop (Blocker #1),
and a full golden-set end-to-end run — so a change that breaks a safety control fails loudly.

## 2. Why this folder exists

`docs/CLAUDE.md` says the safety controls are enforced by tests, not prose: "if a safety test is
in your way, the change is wrong, not the test." This folder is where those guarantees are made
executable and kept honest against the golden fixture.

## 3. How it fits into the overall architecture

```
 tests/ ─ import ─▶ src.state, src.nodes.*, src.hitl.interrupts, src.graph.build_graph
        ─ run    ─▶ build_graph().invoke(...) on sample_data/sample_suite (run_mode="automated")
        ─ assert ─▶ against sample_data/expected_findings.json (the golden answer key)
 conftest.py ─ isolates ─▶ src.memory.store to a per-test temp dir
```

## 4. Files inside the folder

`conftest.py`, `test_state.py`, `test_coverage_gate.py`, `test_validation_loop.py`,
`test_graph_e2e.py`.

## 5. Responsibilities of each file

- **`conftest.py`** — autouse fixture `isolated_memory(tmp_path, monkeypatch)` redirects the
  memory store dir to a fresh temp path per test (no cross-test state bleed).
- **`test_state.py`** — asserts `TestOptimiserState` has every required field with correct
  types, and that `tool_errors`/`audit_log` use the `Annotated[list, add]` append reducer.
- **`test_coverage_gate.py`** — Blocker #2: `coverage_floor_gate` routes to `revise` when a
  removal set breaches `DEFAULT_COVERAGE_TARGET` (0.80), passes when removals are cost-free
  duplicates, `revise_node` loops until above floor, and `is_protected` keeps risk-area tests
  (e.g. "payment") off the removal list.
- **`test_validation_loop.py`** — Blocker #1: `route_after_validation` returns
  `approve_tests`/`gap_gen`/`drop_failing` correctly; a full run with a monkeypatched
  always-failing sandbox terminates, caps `gen_retry_count` at `MAX_GEN_RETRIES`, and drops +
  flags (`audit_log` event `dropped_failing_tests`) rather than silently keeping bad tests.
- **`test_graph_e2e.py`** — module-scoped `outputs` fixture runs the whole graph on
  `sample_data/sample_suite` in `automated` mode; asserts the four deliverables and required
  audit nodes exist and that findings (duplicate cluster, flaky/slow tests, coverage gap,
  floor ≥ 0.80, protected test never removed) match `expected_findings.json`.

## 6. Inputs

`src.*` modules, the `sample_data/` fixture, and the golden `expected_findings.json`. Some tests
`monkeypatch` `sandbox.validate` to force failures.

## 7. Outputs

Pass/fail results (via `pytest`). No files written; memory writes go to the temp dir.

## 8. Dependencies

`pytest` (configured by root `pytest.ini`: `pythonpath=.`, `testpaths=tests`), `src.config`,
`src.state`, `src.nodes.*`, `src.hitl.interrupts`, `src.graph`, `src.memory.store`.

## 9. Which folders call/use it

CI and developers via `pytest`. It is a top-level consumer of `src/`.

## 10. Which folders it calls/uses

`src/` (all layers, via `build_graph` and direct imports), `sample_data/` (fixture + golden set).

## 11. Runtime execution flow

```
pytest → conftest isolates memory dir
  test_state          : import schema, assert fields/reducers
  test_coverage_gate  : build states, call coverage_floor_gate / revise_node / is_protected
  test_validation_loop: unit-check route_after_validation; full invoke with failing sandbox → assert termination
  test_graph_e2e      : build_graph().invoke(sample suite, automated) → compare to expected_findings.json
```

Run: `pytest` (all) or `pytest tests/test_graph_e2e.py -v` (one file).

## 12. Common debugging locations

- **Schema test fails** → `src/state.py` fields/reducers.
- **Gate test fails** → `coverage_floor_gate`/`revise_node` in `prioritisation.py`, `_coverage_model`.
- **Loop test hangs/fails** → `route_after_validation` + `MAX_GEN_RETRIES` in `validation.py`.
- **E2E finding mismatch** → the node that produces it, or a drifted `sample_data/` (regenerate the fixture).
- **Cross-test contamination** → `conftest.py` memory-dir redirect.
