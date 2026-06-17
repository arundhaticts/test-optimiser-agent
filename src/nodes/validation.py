"""
Node 8 — Static Validation (sandbox)  +  bounded-loop routing (Blocker #1).

validation_node statically checks each generated test in the sandbox (syntax only,
never executes). route_after_validation enforces the hard ceiling: valid -> HITL 3;
invalid with retries left -> regenerate; retries exhausted -> drop_failing. drop_failing
drops the still-invalid tests, flags them for the human, and lets the run proceed —
the loop can never spin forever.
"""

from src.config import MAX_GEN_RETRIES
from src.observability import audit
from src.tools import sandbox


def validation_node(state) -> dict:
    generated = state.get("generated_tests", [])
    checked, all_valid = [], True
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
    """The BOUNDED LOOP. Guarantees termination after MAX_GEN_RETRIES."""
    if state.get("validation_passed"):
        return "approve_tests"
    if state.get("gen_retry_count", 0) >= MAX_GEN_RETRIES:
        return "drop_failing"
    return "gap_gen"


def drop_failing_node(state) -> dict:
    """Fallback: drop still-invalid tests, flag them, proceed to HITL 3."""
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
