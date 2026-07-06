# `src/memory/` — Long-term per-project store

## 1. Purpose

The agent's **long-term memory**: a per-project JSON store of prior decisions (so a rejected
suggestion is never re-offered), human-pinned **protected** tests (never auto-removed), and
**known-flaky** tests (context for future triage). This is the Phase-5 feedback loop that makes
the agent improve across runs.

## 2. Why this folder exists

State (`src/state.py`) lives only for one run. Some facts must **survive between runs** —
"the team already said no to removing X", "Y is pinned", "Z is confirmed flaky". A tiny,
dependency-free JSON store keeps that durable without a database.

## 3. How it fits into the overall architecture

```
 retrieval_node ─ reads ─▶ store.get_prior_decisions / get_known_flaky / get_protected_tests
 hitl.interrupts.is_protected ─ reads ─▶ store.get_protected_tests
 report_node ─ writes ─▶ store.save_decision / record_flaky
                              │
                              ▼
              .agent_memory/{project_id}.json  (one file per project)
```

## 4. Files inside the folder

`__init__.py` (package marker), `store.py`.

## 5. Responsibilities of each file

- **`store.py`** — a per-project JSON store keyed by `project_id`:
  - `save_decision(project_id, decision)` / `get_prior_decisions(project_id)` — decision history
    (`{test_id, action, accepted}`).
  - `record_flaky(project_id, test_id)` / `get_known_flaky(project_id)` — confirmed-flaky set
    (context only; does **not** protect from removal).
  - `add_protected(project_id, test_id)` / `get_protected_tests(project_id)` — human-pinned tests
    that are never auto-removed.
  - `_file` (maps `project_id` → `.agent_memory/{safe_id}.json`), `_load`, `_save` (create dir,
    read/write JSON; fresh empty structure when absent).

## 6. Inputs

`project_id` (string, used as filename), `test_id`, decision dicts.

## 7. Outputs

JSON files under `.agent_memory/` (gitignored); lists/dicts returned by the `get_*` functions.

## 8. Dependencies

Stdlib only (`json`, `pathlib`). No config, no third-party packages.

## 9. Which folders call/use it

`src/nodes/retrieval.py` and `src/nodes/report.py`; `src/hitl/interrupts.py` (via `is_protected`).
`tests/conftest.py` redirects the store directory to a temp path for isolation.

## 10. Which folders it calls/uses

None — it is a leaf that only touches the local `.agent_memory/` directory.

## 11. Runtime execution flow

```
retrieval_node → get_prior_decisions / get_protected_tests  (seed context, pin tests)
hitl_removals  → is_protected(test_id) → get_protected_tests  (block pinned removals)
report_node    → save_decision(...) for each approved action
               → record_flaky(...) for confirmed flaky tests
(next run)     → those facts are read back in retrieval
```

## 12. Common debugging locations

- **A rejected suggestion keeps reappearing** → `save_decision`/`get_prior_decisions` and
  whether `report_node` actually persisted it.
- **A pinned test got removed** → `get_protected_tests` + `is_protected` (and `risk_areas`).
- **Tests bleed state into each other** → `tests/conftest.py` temp-dir redirect of the store.
- **Wrong file targeted** → `_file` slug mapping of `project_id`.
