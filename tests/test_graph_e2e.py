"""
End-to-end: run the full graph on the sample_data/ suite, auto-answering the 3 HITL
interrupts, and assert the four outputs are produced and the audit_log is complete.

Also assert the run reproduces sample_data/expected_findings.json (the golden set):
the near-duplicate cluster, the flaky test (test_checkout_total), the slow test
(test_payment_gateway), and the AC-3 coverage gap. This is regression coverage on
the agent's analysis quality, not just that it ran without crashing.
"""

import json
from pathlib import Path

import pytest

from src.graph import build_graph

GOLDEN = json.loads(
    (Path(__file__).resolve().parents[1] / "sample_data" / "expected_findings.json")
    .read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def outputs():
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "e2e"}}
    state = graph.invoke({
        "project_id": "e2e",
        "suite_path": "sample_data/sample_suite",
        "optimization_goal": "speed",
        "coverage_target": 0.80,
        "risk_areas": ["payment"],
        "run_mode": "automated",      # auto-approves recommended at each checkpoint
        "gen_retry_count": 0,
        "audit_log": [], "tool_errors": [],
    }, config=cfg)
    return state["final_outputs"]


def test_four_deliverables_present(outputs):
    for key in ("scorecard", "coverage_gap_map",
                "redundancy_flakiness_report", "optimised_plan"):
        assert key in outputs and outputs[key]


def test_audit_log_is_complete(outputs):
    events = [e["node"] for e in outputs["audit_log"]]
    for node in ("intake", "coverage", "redundancy", "scoring",
                 "prioritisation", "assemble", "report"):
        assert node in events


def test_reproduces_golden_duplicate_cluster(outputs):
    clusters = [set(f["cluster"])
                for f in outputs["redundancy_flakiness_report"]["redundancy_flags"]]
    expected = set(GOLDEN["redundancy_flags"][0]["cluster"])
    assert expected in clusters


def test_reproduces_golden_flaky_and_slow(outputs):
    report = outputs["redundancy_flakiness_report"]
    flaky = {f["test_id"] for f in report["flakiness_flags"]}
    slow = {f["test_id"] for f in report["slow_flags"]}
    assert GOLDEN["flakiness_flags"][0]["test_id"] in flaky
    assert GOLDEN["slow_flags"][0]["test_id"] in slow


def test_reproduces_golden_coverage_map_and_gap(outputs):
    cgm = outputs["coverage_gap_map"]
    for cid, tests in GOLDEN["coverage_map"].items():
        assert cgm["coverage_map"].get(cid) == tests
    gap_ids = {g["criterion_id"] for g in cgm["gaps"]}
    assert GOLDEN["coverage_gaps"][0]["criterion_id"] in gap_ids


def test_coverage_floor_held_and_no_pinned_removed(outputs):
    plan = outputs["optimised_plan"]
    assert plan["projected_coverage"] >= 0.80
    assert "test_payment_gateway" not in plan["proposed"]["removed"]  # risk-area pinned
