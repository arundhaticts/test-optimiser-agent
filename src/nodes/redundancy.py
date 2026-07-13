"""
Node 3 — Redundancy & Flakiness Detection.

Duplicate detection via semantic clustering (nlp/clustering); flakiness/slow triage from
CI history (tools/ci_history) using FLAKY_FAIL_RATE / SLOW_TEST_SECONDS. Every flag
carries evidence. Insufficient history degrades to 'needs more data' — never asserted.

Architecture position: Node 3 of 10 — Redundancy & Flakiness; runs after coverage,
before retrieval.
Called by: the graph (src/graph.py).
Data in: normalised_suite.
Data out: redundancy_flags, flakiness_flags, slow_flags, audit_log[+].
"""

from src.config import FLAKY_FAIL_RATE, SLOW_TEST_SECONDS
from src.observability import audit
from src.tools import ci_history
from src.nlp.clustering import cluster_duplicates


def redundancy_node(state) -> dict:
    """Flag near-duplicate clusters and triage tests into flaky/slow from CI history.

    Purpose: detect duplicate test clusters (merge candidates) and, per test, classify
        flaky/slow using CI fail-rate and average runtime thresholds, each with evidence.
    Inputs: state — reads normalised_suite.
    Outputs: dict with redundancy_flags, flakiness_flags, slow_flags, audit_log[+].
    Side effects: reads CI history via ci_history.get_history (mock_ci_history.json);
        appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: cluster_duplicates, ci_history.get_history, audit.
    """
    suite = state.get("normalised_suite", [])

    # WHY: build merge-candidate flags from near-duplicate clusters — keep the first test
    # of each cluster, mark the rest redundant, and attach evidence for the human at HITL 1.
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

    # WHY: triage each test against CI history — flaky if fail-rate crosses FLAKY_FAIL_RATE,
    # slow if avg runtime crosses SLOW_TEST_SECONDS. Tests with no history are only counted
    # (no_history), never asserted flaky/slow.
    # --- Flakiness & slow triage ---
    # WHY: read the optional per-run ci_history_path once so an uploaded CI-history file
    # (benchmark) drives flaky/slow triage instead of the fixture (None => fixture).
    ci_path = state.get("ci_history_path")
    flakiness_flags, slow_flags, no_history = [], [], 0
    for t in suite:
        hist = ci_history.get_history(t["id"], ci_path)
        # WHY: no runs recorded -> insufficient evidence; count and skip, don't guess.
        if not hist or not hist.get("runs"):
            no_history += 1
            continue
        fail_rate = hist["fails"] / hist["runs"]
        # WHY: threshold check — fail-rate at/above the flaky bound quarantines (reversibly).
        if fail_rate >= FLAKY_FAIL_RATE:
            flakiness_flags.append({
                "test_id": t["id"], "kind": "flaky",
                "fail_rate": round(fail_rate, 3),
                "evidence": f"{hist['fails']}/{hist['runs']} fails = {fail_rate:.0%}, "
                            f">= {FLAKY_FAIL_RATE:.0%} threshold.",
                "action": "quarantine (reversible) — gated at HITL 1",
            })
        # WHY: threshold check — average runtime at/above the slow bound re-tiers out of smoke.
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
