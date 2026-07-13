"""
Node 10 — Render Outputs & Update Memory.

Renders the four deliverables (Test Health Scorecard, Coverage & Gap Map, Redundancy &
Flakiness Report, Optimised Plan + generated tests + context sources) into final_outputs,
surfacing tool_errors so degraded results are visible. Then closes the Phase 5 feedback
loop: records the run's decisions and newly-confirmed flaky tests to long-term memory.

Architecture position: Node 10 of 10 — Report; the pipeline's final node, runs after
assemble, before END.
Called by: the graph (src/graph.py).
Data in: final_outputs, scorecard, approved_generated_tests, coverage_gaps,
coverage_map, projected_coverage, redundancy_flags, flakiness_flags, slow_flags,
retrieved_context, tool_errors, audit_log, project_id, approved_removals.
Data out: final_outputs (all 4 deliverables + extras; plus a `benchmark` section when an
expected-findings answer key is available), audit_log[+].
"""

from src.observability import audit
from src.memory import store as memory
from src.tools import expected_findings as expected_findings_tool
from src.tools.tool_wrapper import call_tool, tool_error_entry


def _id_metrics(expected_ids, actual_ids) -> dict:
    """Compare two id sets and return matched/missing/extra + precision/recall.

    Purpose: grade a flat category (flaky / slow / coverage_gaps) of the run's findings
        against the expected ids.
    Inputs: expected_ids, actual_ids (iterables of str; falsy/None entries dropped).
    Outputs: dict {expected, actual, matched, missing, extra, precision, recall}.
    Side effects: None (pure).
    Called by: _benchmark.
    Calls: set operations.
    """
    exp = {i for i in expected_ids if i}
    act = {i for i in actual_ids if i}
    matched = exp & act
    # WHY: precision = of what we flagged, how much was expected; recall = of what was
    # expected, how much we caught. None (not 0) when a side is empty so it reads as "n/a".
    precision = round(len(matched) / len(act), 3) if act else None
    recall = round(len(matched) / len(exp), 3) if exp else None
    return {"expected": sorted(exp), "actual": sorted(act),
            "matched": sorted(matched), "missing": sorted(exp - act),
            "extra": sorted(act - exp), "precision": precision, "recall": recall}


def _cluster_metrics(expected_clusters, actual_clusters) -> dict:
    """Compare duplicate clusters (order-independent) and return the same-shaped metrics.

    Purpose: grade the duplicate-cluster category, treating each cluster as an unordered
        set so cluster/member ordering never affects the match.
    Inputs: expected_clusters, actual_clusters (iterables of id lists).
    Outputs: dict {matched, missing, extra, precision, recall, expected_count, actual_count}.
    Side effects: None (pure).
    Called by: _benchmark.
    Calls: frozenset / set operations.
    """
    exp = {frozenset(c) for c in expected_clusters if c}
    act = {frozenset(c) for c in actual_clusters if c}
    matched = exp & act
    precision = round(len(matched) / len(act), 3) if act else None
    recall = round(len(matched) / len(exp), 3) if exp else None
    # WHY: clusters aren't JSON-serialisable as sets — emit each as a sorted id list.
    return {"matched": [sorted(c) for c in matched],
            "missing": [sorted(c) for c in exp - act],
            "extra": [sorted(c) for c in act - exp],
            "precision": precision, "recall": recall,
            "expected_count": len(exp), "actual_count": len(act)}


def _benchmark(expected: dict, state) -> dict:
    """Grade the run's actual findings against an expected-findings answer key.

    Purpose: produce a benchmark comparison (per-category matched/missing/extra + an overall
        precision/recall summary) so an uploaded golden set turns a run into a scored eval.
    Inputs: expected — the golden dict (duplicates / flaky / slow / coverage_gaps); state —
        the run state (redundancy_flags, flakiness_flags, slow_flags, coverage_gaps).
    Outputs: dict {categories: {duplicates, flaky, slow, coverage_gaps}, summary: {...}}.
    Side effects: None (pure).
    Called by: report_node.
    Calls: _id_metrics, _cluster_metrics.
    """
    # WHY: map the agent's finding shapes to the golden file's shapes, then grade each.
    cats = {
        "duplicates": _cluster_metrics(
            [d.get("tests", []) for d in expected.get("duplicates", [])],
            [f.get("cluster", []) for f in state.get("redundancy_flags", [])]),
        "flaky": _id_metrics(
            [f.get("test") for f in expected.get("flaky", [])],
            [f.get("test_id") for f in state.get("flakiness_flags", [])]),
        "slow": _id_metrics(
            [s.get("test") for s in expected.get("slow", [])],
            [s.get("test_id") for s in state.get("slow_flags", [])]),
        "coverage_gaps": _id_metrics(
            [g.get("criterion_id") for g in expected.get("coverage_gaps", [])],
            [g.get("criterion_id") for g in state.get("coverage_gaps", [])]),
    }
    # WHY: roll the per-category counts into one headline precision/recall so a benchmark run
    # has a single at-a-glance score (duplicates count as whole clusters).
    matched = sum(len(c["matched"]) for c in cats.values())
    expected_total = (cats["duplicates"]["expected_count"]
                      + sum(len(cats[k]["expected"]) for k in ("flaky", "slow", "coverage_gaps")))
    actual_total = (cats["duplicates"]["actual_count"]
                    + sum(len(cats[k]["actual"]) for k in ("flaky", "slow", "coverage_gaps")))
    return {
        "categories": cats,
        "summary": {
            "expected_total": expected_total,
            "actual_total": actual_total,
            "matched_total": matched,
            "missing_total": expected_total - matched,
            "extra_total": actual_total - matched,
            "recall": round(matched / expected_total, 3) if expected_total else None,
            "precision": round(matched / actual_total, 3) if actual_total else None,
        },
    }


def report_node(state) -> dict:
    """Render the four deliverables and persist decisions to long-term memory.

    Purpose: assemble the scorecard, coverage/gap map, redundancy/flakiness report, and
        generated tests into final_outputs; annotate gaps now addressed by approved tests;
        then save decisions and confirmed-flaky tests to memory (Phase-5 feedback loop).
    Inputs: state — reads final_outputs, scorecard, approved_generated_tests,
        coverage_gaps, coverage_map, projected_coverage, redundancy_flags,
        flakiness_flags, slow_flags, retrieved_context, tool_errors, audit_log,
        project_id, approved_removals.
    Outputs: dict with final_outputs (all deliverables) and audit_log[+].
    Side effects: memory writes (save_decision, record_flaky) to
        .agent_memory/{project_id}.json; appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: audit, memory.save_decision, memory.record_flaky.
    """
    final = dict(state.get("final_outputs", {}))

    final["scorecard"] = state.get("scorecard", {})
    # Mark gaps that an APPROVED generated test now addresses, so the coverage view
    # reflects the human's decision. The criterion stays a "gap" (the drafted test isn't
    # merged/verified yet) but is annotated with the test that addresses it.
    # WHY: keep only dict entries (approved list may hold ids), then build a
    # criterion_id -> generated_test_id map from approved tests that name a criterion.
    approved_gen = [g for g in state.get("approved_generated_tests", []) if isinstance(g, dict)]
    addressed = {g.get("criterion_id"): g.get("id") for g in approved_gen if g.get("criterion_id")}
    # WHY: annotate each gap that an approved test addresses with "addressed_by"; copy each
    # gap before mutating so source state isn't changed. The gap stays a gap (not verified).
    gaps = []
    for gp in state.get("coverage_gaps", []):
        gp = dict(gp)
        if gp.get("criterion_id") in addressed:
            gp["addressed_by"] = addressed[gp["criterion_id"]]
        gaps.append(gp)
    final["coverage_gap_map"] = {
        "coverage_map": state.get("coverage_map", {}),
        "gaps": gaps,
        "projected_coverage": state.get("projected_coverage"),
    }
    final["redundancy_flakiness_report"] = {
        "redundancy_flags": state.get("redundancy_flags", []),
        "flakiness_flags": state.get("flakiness_flags", []),
        "slow_flags": state.get("slow_flags", []),
    }
    final["generated_tests"] = state.get("approved_generated_tests", [])
    final["context_sources"] = state.get("retrieved_context", [])
    final["tool_errors"] = state.get("tool_errors", [])

    # WHY: when an expected-findings answer key is available (sample golden on a demo run, or
    # an uploaded key on a benchmark run), grade the run's actual findings against it and
    # attach a `benchmark` section. "" (upload without a key) => load returns None => no
    # benchmark; a bad key degrades to a surfaced tool_error rather than failing the run.
    exp_res = call_tool(expected_findings_tool.load, state.get("expected_findings_path"))
    benchmark = None
    if exp_res["ok"] and exp_res["data"]:
        benchmark = _benchmark(exp_res["data"], state)
        final["benchmark"] = benchmark
    elif not exp_res["ok"]:
        final["tool_errors"] = final["tool_errors"] + [tool_error_entry(
            "expected_findings", exp_res["error"], "benchmark skipped")]

    # WHY: embed the full accumulated audit trail plus this node's own entry into
    # final_outputs so the deliverable carries the complete trace.
    # Include this node's own entry so the embedded trail is complete.
    entry = audit("report", "rendered_outputs",
                  deliverables=4, tool_errors=len(final["tool_errors"]),
                  benchmark=bool(benchmark))
    final["audit_log"] = state.get("audit_log", []) + [entry]

    # WHY: persist outcomes so future runs learn — every removal candidate (flaky tests +
    # redundant cluster members) is saved with whether the human accepted it, and flaky
    # tests the human approved for removal are recorded as confirmed-flaky.
    # --- Phase 5 feedback loop: persist decisions + confirmed flaky tests ---
    project_id = state.get("project_id")
    approved = set(state.get("approved_removals", []))
    # WHY: candidate set = all flaky test ids plus every redundant-cluster member.
    candidates = {f["test_id"] for f in state.get("flakiness_flags", [])}
    for f in state.get("redundancy_flags", []):
        candidates.update(f.get("redundant", []))
    for tid in candidates:
        memory.save_decision(project_id, {"test_id": tid, "action": "remove",
                                          "accepted": tid in approved})
    # WHY: only flaky tests the human actually approved for removal become confirmed-flaky.
    for f in state.get("flakiness_flags", []):
        if f["test_id"] in approved:
            memory.record_flaky(project_id, f["test_id"])

    return {"final_outputs": final, "audit_log": [entry]}
