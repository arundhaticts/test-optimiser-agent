"""
Node 8 — Static Validation (sandbox)  +  bounded-loop routing (Blocker #1).

validation_node statically checks each generated test in the sandbox (syntax only,
never executes). route_after_validation enforces the hard ceiling: valid -> HITL 3;
invalid with retries left -> regenerate; retries exhausted -> drop_failing. drop_failing
drops the still-invalid tests, flags them for the human, and lets the run proceed —
the loop can never spin forever.

Architecture position: Node 8 of 10 — Static Validation; runs after gap_generation,
before HITL 3 (approve tests). This module also holds route_after_validation (a ROUTER
after validation) and drop_failing_node (an AUX node when retries are exhausted).
Called by: the graph (src/graph.py).
Data in: generated_tests, validation_passed, gen_retry_count (see each function).
Data out: generated_tests, validation_passed, needs_regen, audit_log[+].
"""

from src.config import MAX_GEN_RETRIES
from src.observability import audit
from src.tools import sandbox


def validation_node(state) -> dict:
    """Statically validate each generated test in the sandbox (syntax only).

    Purpose: run every drafted test through the sandbox syntax check, tag each valid or
        with its error, and report whether the whole batch passed.
    Inputs: state — reads generated_tests.
    Outputs: dict with generated_tests (tagged valid/error), validation_passed,
        needs_regen, audit_log[+].
    Side effects: sandbox.validate spawns a Python subprocess per test (never executes
        against production); appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: sandbox.validate, audit.
    """
    generated = state.get("generated_tests", [])
    checked, all_valid = [], True
    # WHY: validate each test independently; copy before tagging so the source dict isn't
    # mutated, and clear all_valid the moment any test fails so the router can react.
    for t in generated:
        result = sandbox.validate(t.get("code", ""))
        t = dict(t)
        t["valid"] = result["valid"]
        if not result["valid"]:
            t["error"] = result["error"]
            all_valid = False
        checked.append(t)
    return {
        "generated_tests": checked,
        "validation_passed": all_valid,
        "needs_regen": not all_valid,
        "audit_log": [audit("validation", "validated",
                            total=len(checked),
                            valid=sum(1 for t in checked if t["valid"]),
                            passed=all_valid)],
    }


def route_after_validation(state) -> str:
    """The BOUNDED LOOP. Guarantees termination after MAX_GEN_RETRIES.

    Purpose: ROUTER — pick the next node based on validation result and retry budget.
    Inputs: state — reads validation_passed, gen_retry_count.
    Outputs: the next node name (str) — one of three outcomes below.
    Side effects: None (pure); writes no state.
    Called by: the graph (conditional edges after validation).
    Calls: (none).
    """
    # WHY: outcome 1 — all tests valid -> proceed to HITL 3.
    if state.get("validation_passed"):
        return "approve_tests"
    # WHY: outcome 2 — retries exhausted at the MAX_GEN_RETRIES ceiling -> stop looping and
    # hand off to drop_failing so the run always terminates (Blocker #1).
    if state.get("gen_retry_count", 0) >= MAX_GEN_RETRIES:
        return "drop_failing"
    # WHY: outcome 3 — invalid but retries remain -> loop back to regenerate.
    return "gap_gen"


def drop_failing_node(state) -> dict:
    """Fallback: drop still-invalid tests, flag them, proceed to HITL 3.

    Purpose: AUX node reached when retries are exhausted — keep the valid tests, flag the
        still-invalid ones for humans, and let the run proceed.
    Inputs: state — reads generated_tests.
    Outputs: dict with generated_tests (kept + flagged-dropped), validation_passed=True,
        audit_log[+].
    Side effects: appends an audit log entry.
    Called by: the graph (routed to by route_after_validation).
    Calls: audit.
    """
    # WHY: split into kept (valid) vs dropped (still-invalid); dropped tests are retained in
    # the output but flagged so nothing silently disappears.
    dropped, kept = [], []
    for t in state.get("generated_tests", []):
        if t.get("valid"):
            kept.append(t)
        else:
            t = dict(t)
            t["dropped"] = True
            t["flag"] = "could not auto-generate after retries — manual attention needed"
            dropped.append(t)
    return {
        "generated_tests": kept + dropped,
        "validation_passed": True,        # the run proceeds; dropped tests are flagged
        "audit_log": [audit("drop_failing", "dropped_failing_tests",
                            dropped=len(dropped), kept=len(kept))],
    }
