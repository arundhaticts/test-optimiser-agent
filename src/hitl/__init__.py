"""Human-in-the-loop interrupt payloads and handlers.

Architecture position:
    hitl/ = the 3 human approval interrupts and the agent's safety boundary.
    Nothing destructive (removals, merges, generated tests) enters the plan
    without a human decision written into state at one of these checkpoints.

Called by:
    src/graph.py wires the 3 HITL nodes into the spine; prioritisation and
    revise reach in via is_protected to keep pinned tests off removal lists.

Data in:  run state (flags, plan, generated tests, run_mode, risk_areas).
Data out: approved_removals / approved_priority / approved_generated_tests.
"""
