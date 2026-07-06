# `src/hitl/` — Human-in-the-loop checkpoints

## 1. Purpose

The three **human-in-the-loop (HITL) checkpoints** where the graph pauses, shows the human an
evidence-rich payload, and only continues once a decision is written into state. This is what
makes the agent **recommend, never delete**: nothing destructive happens without sign-off.

## 2. Why this folder exists

Autonomy is capped at L3: the agent proposes, humans approve. Concentrating all `interrupt()`
logic, the resume-envelope handling, and the "which tests are off-limits" rule in one module
keeps that safety boundary auditable and impossible to bypass by accident.

## 3. How it fits into the overall architecture

```
 scoring ─▶ hitl_removals  (interrupt 1: approve removals/quarantine/merge)
 revise  ─▶ hitl_priority  (interrupt 2: approve smoke/regression/full tiers)
 drop_failing / validation ─▶ hitl_generated (interrupt 3: approve generated tests)

 interrupt(payload) ⇄ Command(resume={"__hitl__": decision})
        │                        ▲
   main.py (stdin)          api.py (POST /runs/{id}/resume)
```

`is_protected()` is imported by `src/nodes/prioritisation.py` too, so pinned tests are excluded
before a removal is ever proposed.

## 4. Files inside the folder

`__init__.py` (package marker), `interrupts.py`.

## 5. Responsibilities of each file

- **`interrupts.py`**
  - **Three HITL nodes** — `hitl_removals_node`, `hitl_priority_node`, `hitl_generated_node`.
    In `interactive` mode each calls `interrupt(payload)` and waits; in `automated` mode each
    auto-approves the recommended (reversible) set.
  - **Payload builders** — `build_removal_payload`, `build_priority_payload`,
    `build_generated_tests_payload` assemble evidence (candidates, reasons, pinned flags,
    tiers, valid/dropped tests, recommended defaults).
  - **`is_protected(test_id, state) -> bool`** — True if the test matches `risk_areas`
    (case-insensitive substring) **or** `memory.get_protected_tests()`. Never removable.
  - **`_decision(raw, default)`** — unwraps the `{"__hitl__": value}` resume envelope so a
    falsy-but-valid approval (empty list = "keep everything") is not dropped.
  - **Safety re-filter** — `hitl_removals_node` re-drops any pinned test that slipped into an
    approved list before writing `approved_removals`.

## 6. Inputs

State: `run_mode`, `flakiness_flags`, `redundancy_flags`, `prioritised_plan`,
`generated_tests`, `risk_areas`, `project_id`; the resume value from `main.py`/`api.py`.

## 7. Outputs

State updates: `approved_removals`, `approved_priority`, `approved_generated_tests`, plus
`audit_log` entries. Interrupt payloads surfaced to the CLI/HTTP caller/frontend.

## 8. Dependencies

`langgraph.types.interrupt`, `src.memory.store` (`get_protected_tests`),
`src.observability.audit`.

## 9. Which folders call/use it

`src/graph.py` (wires the 3 nodes); `src/nodes/prioritisation.py` (`is_protected`);
`tests/` (`is_protected`, e2e auto-approval); `main.py`/`api.py` drive the resumes.

## 10. Which folders it calls/uses

`src/memory/` (protected tests), `src/observability.py`.

## 11. Runtime execution flow

```
interactive: node → interrupt(build_*_payload(state)) → PAUSE
             caller shows payload, collects decision → Command(resume={"__hitl__": decision})
             node resumes → _decision() unwraps → (safety re-filter) → write approved_* → continue
automated  : node → auto-approve recommended set → write approved_* → continue (no pause)
```

## 12. Common debugging locations

- **Empty approval ("keep all") ignored** → `_decision` envelope unwrapping.
- **Pinned test still removed** → `is_protected` + `hitl_removals_node` re-filter + `risk_areas`.
- **HTTP resume does nothing** → the `{"__hitl__": …}` wrapping in `api.py` vs `_decision`.
- **Graph never pauses** → `run_mode` is `automated`, or checkpointer missing in `graph.py`.
- **Payload missing evidence** → the relevant `build_*_payload` and the state keys it reads.
