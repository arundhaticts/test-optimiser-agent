"""
Node 3 — Redundancy & Flakiness Detection.

Duplicate detection via semantic clustering (nlp/clustering); flakiness/slow triage from
CI history (tools/ci_history) using FLAKY_FAIL_RATE / SLOW_TEST_SECONDS. Every flag
carries evidence. Insufficient history degrades to 'needs more data' — never asserted.
"""

from src.config import FLAKY_FAIL_RATE, SLOW_TEST_SECONDS
from src.observability import audit
from src.tools import ci_history
from src.nlp.clustering import cluster_duplicates


def redundancy_node(state) -> dict:
    suite = state.get("normalised_suite", [])

    # --- Duplicates ---
    clusters = cluster_duplicates(suite)
    redundancy_flags = [
        {
            "kind": "near_duplicate",
            "cluster": cluster,
            "keep": cluster[0],
            "redundant": cluster[1:],
            "evidence": f"{len(cluster)} tests cluster above the duplicate threshold.",
            "action": "merge",
        }
        for cluster in clusters
    ]

    # --- Flakiness & slow triage ---
    flakiness_flags, slow_flags, no_history = [], [], 0
    for t in suite:
        hist = ci_history.get_history(t["id"])
        if not hist or not hist.get("runs"):
            no_history += 1
            continue
        fail_rate = hist["fails"] / hist["runs"]
        if fail_rate >= FLAKY_FAIL_RATE:
            flakiness_flags.append({
                "test_id": t["id"], "kind": "flaky",
                "fail_rate": round(fail_rate, 3),
                "evidence": f"{hist['fails']}/{hist['runs']} fails = {fail_rate:.0%}, "
                            f">= {FLAKY_FAIL_RATE:.0%} threshold.",
                "action": "quarantine (reversible) — gated at HITL 1",
            })
        if hist.get("avg_seconds", 0) >= SLOW_TEST_SECONDS:
            slow_flags.append({
                "test_id": t["id"], "kind": "slow",
                "avg_seconds": hist["avg_seconds"],
                "evidence": f"{hist['avg_seconds']}s avg, >= {SLOW_TEST_SECONDS}s threshold.",
                "action": "re-tier out of smoke; candidate for optimisation",
            })

    return {
        "redundancy_flags": redundancy_flags,
        "flakiness_flags": flakiness_flags,
        "slow_flags": slow_flags,
        "audit_log": [audit("redundancy", "flagged",
                            duplicate_clusters=len(redundancy_flags),
                            flaky=len(flakiness_flags), slow=len(slow_flags),
                            no_history=no_history)],
    }
