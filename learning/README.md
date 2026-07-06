# `learning/` — Standalone LangGraph tutorials

## 1. Purpose

Three tiny, self-contained LangGraph scripts that teach the exact mechanics the real agent
relies on — state + nodes, conditional branching/loops, and interrupt/resume — in isolation,
before you meet them tangled together in `src/graph.py`.

## 2. Why this folder exists

The production graph combines several LangGraph features at once (a linear spine, two loops,
three interrupts, a checkpointer). New contributors learn faster by seeing each concept alone.
These files are **learning aids only** — nothing in `src/` imports them.

## 3. How it fits into the overall architecture

They mirror, in miniature, the patterns used by the agent:

```
 01_counter_graph.py     ↔ the linear spine (intake→…→report), plain state passing
 02_conditional_branch.py↔ coverage_floor_gate ⇄ revise  and  validation retry loop
 03_interrupt_resume.py  ↔ the 3 HITL checkpoints (interrupt + checkpointer + resume)
```

## 4. Files inside the folder

`01_counter_graph.py`, `02_conditional_branch.py`, `03_interrupt_resume.py`.

## 5. Responsibilities of each file

- **`01_counter_graph.py`** — a 3-node linear graph (A→B→C) where each node mutates shared
  state; shows the "clipboard" filling up. No LLM, no tools.
- **`02_conditional_branch.py`** — adds a routing function after a node that either loops back or
  proceeds based on a counter; the exact shape of the gate/validation loops.
- **`03_interrupt_resume.py`** — adds a checkpointer so the graph pauses at `interrupt()`, waits
  for human input, and resumes carrying that answer; the HITL pattern in isolation.

## 6. Inputs

None beyond an initial state dict defined in each script (and stdin for the interrupt demo).

## 7. Outputs

Printed state to the console at each step. No files written.

## 8. Dependencies

`langgraph` only (and its in-memory checkpointer for script 03). No dependency on `src/`.

## 9. Which folders call/use it

None. Run directly by a developer for learning.

## 10. Which folders it calls/uses

None (self-contained).

## 11. Runtime execution flow

```
python learning/01_counter_graph.py      → build graph → invoke → print state after each node
python learning/02_conditional_branch.py → invoke → observe branch/loop decisions
python learning/03_interrupt_resume.py   → invoke → pauses at interrupt → enter input → resumes
```

## 12. Common debugging locations

- **Graph won't compile** → node/edge registration in the script.
- **Loop never exits** → the routing function's counter condition (mirror of the real loops).
- **Interrupt doesn't pause/resume** → the checkpointer setup and the resume value in script 03.
- **`langgraph` import error** → install from the repo's `requirements.txt`.
