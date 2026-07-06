"""LEARNING STEP 2 — conditional edges + loops (the gate/validation pattern).

Extend step 1: after B, a routing function branches to C or loops back to A based
on a counter. This is exactly the pattern of your coverage gate and validation loop.

Architecture position: learning/ = standalone LangGraph tutorials, NOT imported by src/.
Second of three onboarding scripts; it teaches conditional routing + a bounded loop — the
exact mechanic behind the real agent's two loops: coverage_floor_gate<->revise and
route_after_validation<->gap_gen (both in src/nodes/), each capped by a counter so the run
always terminates.

WHY this concept is taught: conditional branching/looping is how the agent enforces its
safety blockers (retry caps, coverage-floor recovery); learning the counter-guarded loop
here makes those real routers readable later.

Called by: a developer, manually (e.g. `python learning/02_conditional_branch.py`); never
by tests or src/.

Data in: none (self-contained). Data out: none persisted (prints state to stdout).
"""
