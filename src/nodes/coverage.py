"""
Node 2 — Coverage & Gap Analysis.

Matches each test to the acceptance criteria it satisfies (semantic similarity), finds
criteria no test covers, ranks gaps by risk, and writes coverage_map / coverage_gaps /
projected_coverage. Criteria come from the test-management connector; if unavailable we
degrade to an empty criteria set (coverage marked low-confidence).
"""

from src.observability import audit
from src.tools import test_management
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.nlp.similarity import match_tests_to_criteria, find_gaps
from src.nodes._coverage_model import coverage_for


def _is_risk(text: str, risk_areas) -> bool:
    low = text.lower()
    return any(r.lower() in low for r in (risk_areas or []))


def coverage_node(state) -> dict:
    suite = state.get("normalised_suite", [])
    risk_areas = state.get("risk_areas", [])

    res = call_tool(test_management.get_acceptance_criteria, state.get("project_id"))
    criteria = res["data"] if res["ok"] else []
    errors = [] if res["ok"] else [tool_error_entry(
        "test_management", res["error"], "no criteria; coverage is low-confidence")]

    matched = match_tests_to_criteria(suite, criteria)
    gaps = find_gaps(criteria, suite)
    # Rank gaps: risk-area criteria first, then by lowest similarity.
    for g in gaps:
        g["risk"] = _is_risk(g["text"], risk_areas)
    gaps.sort(key=lambda g: (not g["risk"], g["max_similarity"]))

    projected = coverage_for(suite, removals=[], redundancy_flags=[])

    return {
        "coverage_map": matched["coverage_map"],
        "coverage_gaps": gaps,
        "projected_coverage": projected,
        "tool_errors": errors,
        "audit_log": [audit("coverage", "analysed",
                            criteria=len(criteria), gaps=len(gaps),
                            projected_coverage=projected,
                            low_confidence=not res["ok"])],
    }
