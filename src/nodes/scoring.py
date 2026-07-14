"""
Node 5 — Health Scoring.

Scores the suite across quality dimensions (coverage, redundancy, flakiness, speed,
determinism, maintainability), each as {score 0-10, reason, action}. When a reasoning
model is configured it is asked to score with prompts/scoring_prompt (strict JSON);
offline it falls back to a deterministic rubric over the analysis results. Dimensions
with no data are reported as 'insufficient evidence', never guessed.

Architecture position: Node 5 of 10 — Health Scoring; the last spine node, runs after
retrieval, before HITL 1 (approve removals).
Called by: the graph (src/graph.py).
Data in: coverage_gaps, redundancy_flags, flakiness_flags, slow_flags, coverage_map,
projected_coverage, normalised_suite.
Data out: scorecard, tool_errors[+], audit_log[+].
"""

import json

from src.llm import complete, drain_usage, extract_json, llm_available, load_prompt
from src.observability import audit
from src.tools.tool_wrapper import TransientError, call_tool, tool_error_entry

_DIMENSIONS = ("coverage", "redundancy", "flakiness", "speed",
               "determinism", "maintainability")


def _clamp(score: int) -> int:
    """Clamp a raw dimension score into the valid 0-10 band.

    Purpose: keep deterministic rubric scores within range.
    Inputs: score (int).
    Outputs: score bounded to [0, 10].
    Side effects: None (pure).
    Called by: _deterministic_scorecard.
    Calls: (none).
    """
    return max(0, min(10, score))


def _deterministic_scorecard(state) -> dict:
    """Compute the 6-dimension scorecard from analysis results, no LLM.

    Purpose: offline/fallback rubric — derive each dimension's score/reason/action from
        gaps, duplicate/flaky/slow flags, coverage map, and projected coverage.
    Inputs: state — reads coverage_gaps, redundancy_flags, flakiness_flags, slow_flags,
        coverage_map, projected_coverage.
    Outputs: scorecard dict keyed by the 6 dimensions.
    Side effects: None (pure).
    Called by: scoring_node.
    Calls: _clamp.
    """
    gaps = state.get("coverage_gaps", [])
    dups = state.get("redundancy_flags", [])
    flaky = state.get("flakiness_flags", [])
    slow = state.get("slow_flags", [])
    coverage_map = state.get("coverage_map", {})
    projected = state.get("projected_coverage", 0.0)

    card: dict[str, dict] = {}

    # WHY: no criteria -> emit the "insufficient evidence" sentinel (score None) rather
    # than guess a coverage number.
    if not coverage_map:
        card["coverage"] = {"score": None, "reason": "no acceptance criteria available",
                            "action": "insufficient evidence"}
    else:
        card["coverage"] = {
            "score": _clamp(round(projected * 10)),
            "reason": f"projected coverage {projected:.0%}; {len(gaps)} gap(s).",
            "action": "generate tests for gaps" if gaps else "hold",
        }

    card["redundancy"] = {
        "score": _clamp(10 - 2 * len(dups)),
        "reason": f"{len(dups)} near-duplicate cluster(s).",
        "action": "merge duplicates" if dups else "hold",
    }
    card["flakiness"] = {
        "score": _clamp(10 - 3 * len(flaky)),
        "reason": f"{len(flaky)} flaky test(s) by CI fail-rate.",
        "action": "quarantine flaky" if flaky else "hold",
    }
    card["speed"] = {
        "score": _clamp(10 - 3 * len(slow)),
        "reason": f"{len(slow)} slow test(s) over threshold.",
        "action": "re-tier / optimise slow tests" if slow else "hold",
    }
    card["determinism"] = {
        "score": _clamp(10 - 3 * len(flaky)),
        "reason": "tracks flakiness — non-deterministic tests erode trust.",
        "action": "stabilise flaky" if flaky else "hold",
    }
    card["maintainability"] = {
        "score": _clamp(8 - len(dups)),
        "reason": f"{len(dups)} duplicate cluster(s) add upkeep cost.",
        "action": "consolidate" if dups else "hold",
    }
    return card


def _llm_scorecard(state) -> dict:
    """Ask the reasoning model to score the suite; raise so call_tool can degrade.

    Purpose: build an evidence summary, prompt the reasoning model for a strict-JSON
        scorecard, and return only the recognised dimensions.
    Inputs: state — reads projected_coverage, coverage_gaps, coverage_map,
        redundancy_flags, flakiness_flags, slow_flags, normalised_suite.
    Outputs: scorecard dict restricted to the known dimensions present in the response.
    Side effects: LLM call (load_prompt + complete); raises TransientError on unusable
        JSON so call_tool retries/degrades. Invoked via call_tool by scoring_node.
    Called by: scoring_node (via call_tool).
    Calls: load_prompt, complete, extract_json, json.dumps.
    """
    # WHY: pass a compact, structured evidence summary (not raw state) so the model scores
    # from the same facts the deterministic rubric would use.
    evidence = {
        "projected_coverage": state.get("projected_coverage", 0.0),
        "coverage_gaps": [g.get("text") for g in state.get("coverage_gaps", [])],
        "has_acceptance_criteria": bool(state.get("coverage_map")),
        "redundancy_clusters": len(state.get("redundancy_flags", [])),
        "flaky_tests": [f.get("test_id") for f in state.get("flakiness_flags", [])],
        "slow_tests": [f.get("test_id") for f in state.get("slow_flags", [])],
        "suite_size": len(state.get("normalised_suite", [])),
    }
    prompt = load_prompt("scoring_prompt") + json.dumps(evidence, indent=2)
    parsed = extract_json(complete(prompt, provider=state.get("provider"), model=state.get("model")))
    # WHY: strict-JSON guard — if the model didn't return a dict with at least one known
    # dimension, raise TransientError so call_tool degrades to the deterministic rubric.
    if not isinstance(parsed, dict) or not any(d in parsed for d in _DIMENSIONS):
        raise TransientError("scoring model returned no usable JSON scorecard")
    # WHY: keep only recognised dimensions, dropping any extraneous keys the model added.
    return {d: parsed[d] for d in _DIMENSIONS if d in parsed}


def scoring_node(state) -> dict:
    """Produce the 6-dimension health scorecard (LLM when available, else rubric).

    Purpose: score the suite; use the reasoning model if configured, otherwise (or on
        any failure) fall back to the deterministic rubric so the run always proceeds.
    Inputs: state — reads the analysis results consumed by the scorers (see module
        Data in).
    Outputs: dict with scorecard, audit_log[+], and tool_errors[+] on LLM fallback.
    Side effects: may make an LLM call (via call_tool(_llm_scorecard)); appends an audit
        log entry.
    Called by: the graph (src/graph.py).
    Calls: llm_available, call_tool(_llm_scorecard), _deterministic_scorecard,
        tool_error_entry, audit.
    """
    # WHY: LLM-available branch — score with the reasoning model; any failure degrades
    # to the deterministic rubric so the run always proceeds (Safety Control #5/#8).
    # When a key is configured, score with the reasoning model; any failure degrades
    # to the deterministic rubric so the run always proceeds (Safety Control #5/#8).
    if llm_available(state.get("provider")):
        result = call_tool(_llm_scorecard, state)
        # WHY: capture token usage from every real LLM call this node made (success or a
        # tokens-spent-but-unusable retry), so the benchmarking client can read it.
        usage = drain_usage()
        # WHY: LLM succeeded -> use its scorecard.
        if result["ok"]:
            return {
                "scorecard": result["data"],
                "llm_usage": usage,
                "audit_log": [audit("scoring", "scored", method="llm",
                                    dimensions=len(result["data"]))],
            }
        # WHY: LLM failed -> deterministic-fallback rubric, and surface the failure as a
        # tool_error so the degrade is visible.
        scorecard = _deterministic_scorecard(state)
        return {
            "scorecard": scorecard,
            "llm_usage": usage,
            "tool_errors": [tool_error_entry("llm:scoring", result["error"],
                                             "fell back to deterministic rubric")],
            "audit_log": [audit("scoring", "scored", method="deterministic-fallback",
                                dimensions=len(scorecard))],
        }

    # WHY: deterministic branch — no LLM configured, score with the rubric directly.
    scorecard = _deterministic_scorecard(state)
    return {
        "scorecard": scorecard,
        "audit_log": [audit("scoring", "scored", method="deterministic",
                            dimensions=len(scorecard))],
    }
