"""LEARNING STEP 3 — checkpointer + interrupt (the HITL pattern).

Add a checkpointer and one interrupt(): the graph pauses, you type an answer, it
resumes carrying that answer. Master this in isolation BEFORE the real HITL nodes.

Architecture position: learning/ = standalone LangGraph tutorials, NOT imported by src/.
Last of three onboarding scripts; it teaches checkpointer + interrupt()/resume — the exact
mechanic behind the agent's three human-in-the-loop checkpoints (hitl_removals,
hitl_priority, hitl_generated in src/hitl/interrupts.py) that make it "recommend, never
delete".

WHY this concept is taught: the interrupt/resume pause is the trickiest LangGraph feature
and the core of the product's safety story; learning it on one tiny graph first makes the
three real checkpoints (and the {"__hitl__": ...} resume envelope) comprehensible.

Called by: a developer, manually (e.g. `python learning/03_interrupt_resume.py`); never by
tests or src/.

Data in: a human decision typed at the interrupt (stdin). Data out: none persisted (prints
the resumed state to stdout; the checkpointer is in-memory).
"""
