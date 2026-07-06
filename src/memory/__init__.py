"""Long-term per-project memory store.

Architecture position:
    memory/ = the durable, per-project store. Unlike run state (src/state.py),
    which lives for a single run, this persists decisions, protected tests, and
    known-flaky tests across runs as JSON under .agent_memory/.

Called by:
    nodes/retrieval (prior decisions), nodes/report (save decisions / flaky),
    and hitl/interrupts (protected-test lookup via is_protected).

Data in:  project_id plus decisions / test ids to persist.
Data out: prior decisions, protected-test ids, known-flaky ids.
"""
