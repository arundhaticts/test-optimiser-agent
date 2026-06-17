"""
Node 5 — Health Scoring.

Scores the suite across quality dimensions (coverage, redundancy, flakiness, speed,
determinism, maintainability), each as {score 0-10, reason, action}. When a reasoning
model is configured it is asked to score with prompts/scoring_prompt (strict JSON);
offline it falls back to a deterministic rubric over the analysis results. Dimensions
with no data are reported as 'insufficient evidence', never guessed.
"""

import json

from src.config import REASONING_MODEL
from src.llm import complete, extract_json, llm_available, load_prompt
from src.observability import audit
from src.tools.tool_wrapper import TransientError, call_tool, tool_error_entry

_DIMENSIONS = ("coverage", "redundancy", "flakiness", "speed",
               "determinism", "maintainability")


def _clamp(score: int) -> int:
    return max(0, min(10, score))


def _deterministic_scorecard(state) -> dict:
    gaps = state.get("coverage_gaps", [])
    dups = state.get("redundancy_flags", [])
    flaky = state.get("flakiness_flags", [])
    slow = state.get("slow_flags", [])
    coverage_map = state.get("coverage_map", {})
    projected = state.get("projected_coverage", 0.0)

    card: dict[str, dict] = {}

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
    """Ask the reasoning model to score the suite; raise so call_tool can degrade."""
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
    parsed = extract_json(complete(prompt, model=REASONING_MODEL))
    if not isinstance(parsed, dict) or not any(d in parsed for d in _DIMENSIONS):
        raise TransientError("scoring model returned no usable JSON scorecard")
    return {d: parsed[d] for d in _DIMENSIONS if d in parsed}


def scoring_node(state) -> dict:
    # When a key is configured, score with the reasoning model; any failure degrades
    # to the deterministic rubric so the run always proceeds (Safety Control #5/#8).
    if llm_available():
        result = call_tool(_llm_scorecard, state)
        if result["ok"]:
            return {
                "scorecard": result["data"],
                "audit_log": [audit("scoring", "scored", method="llm",
                                    dimensions=len(result["data"]))],
            }
        scorecard = _deterministic_scorecard(state)
        return {
            "scorecard": scorecard,
            "tool_errors": [tool_error_entry("llm:scoring", result["error"],
                                             "fell back to deterministic rubric")],
            "audit_log": [audit("scoring", "scored", method="deterministic-fallback",
                                dimensions=len(scorecard))],
        }

    scorecard = _deterministic_scorecard(state)
    return {
        "scorecard": scorecard,
        "audit_log": [audit("scoring", "scored", method="deterministic",
                            dimensions=len(scorecard))],
    }
