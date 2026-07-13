"""
Node 2 — Coverage & Gap Analysis.

Matches each test to the acceptance criteria it satisfies (semantic similarity), finds
criteria no test covers, ranks gaps by risk, and writes coverage_map / coverage_gaps /
projected_coverage. Criteria come from the test-management connector; if unavailable we
degrade to an empty criteria set (coverage marked low-confidence).

Architecture position: Node 2 of 10 — Coverage; runs after intake, before redundancy.
Called by: the graph (src/graph.py).
Data in: normalised_suite, risk_areas, project_id.
Data out: coverage_map, coverage_gaps, projected_coverage, tool_errors[+], audit_log[+].
"""

from src.observability import audit
from src.tools import test_management
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.nlp.similarity import match_tests_to_criteria, find_gaps
from src.nodes._coverage_model import coverage_for


def _is_risk(text: str, risk_areas) -> bool:
    """Test whether a criterion text falls in a configured risk area.

    Purpose: case-insensitive substring check used to rank risk-area gaps first.
    Inputs: text (criterion text); risk_areas (list of risk-area keywords).
    Outputs: True if any risk-area keyword appears in the text.
    Side effects: None (pure).
    Called by: coverage_node.
    Calls: (none).
    """
    low = text.lower()
    return any(r.lower() in low for r in (risk_areas or []))


def coverage_node(state) -> dict:
    """Map tests to acceptance criteria, find and rank gaps, compute baseline coverage.

    Purpose: build the coverage_map, list uncovered criteria as ranked gaps, and record
        baseline projected coverage (no removals applied yet).
    Inputs: state — reads normalised_suite, risk_areas, project_id.
    Outputs: dict with coverage_map, coverage_gaps, projected_coverage, tool_errors[+],
        audit_log[+].
    Side effects: tool call via call_tool(test_management.get_acceptance_criteria)
        (reads sample_criteria.json); appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: call_tool, test_management.get_acceptance_criteria, match_tests_to_criteria,
        find_gaps, _is_risk, coverage_for, tool_error_entry, audit.
    """
    suite = state.get("normalised_suite", [])
    risk_areas = state.get("risk_areas", [])

    # WHY: fetch acceptance criteria via the connector; if unavailable, degrade to an
    # empty criteria set and record a low-confidence tool_error rather than fail.
    # WHY: pass the optional per-run criteria_path so an uploaded criteria file (benchmark)
    # is used instead of the sample fixture when present (None => fixture, unchanged).
    res = call_tool(test_management.get_acceptance_criteria,
                    state.get("project_id"), state.get("criteria_path"))
    criteria = res["data"] if res["ok"] else []
    errors = [] if res["ok"] else [tool_error_entry(
        "test_management", res["error"], "no criteria; coverage is low-confidence")]

    # WHY: match tests to the criteria they satisfy, then find the criteria no test covers.
    matched = match_tests_to_criteria(suite, criteria)
    gaps = find_gaps(criteria, suite)
    # WHY: rank gaps risk-first, then by lowest similarity — the riskiest, least-covered
    # criteria surface at the top so gap generation and humans address them first.
    # Rank gaps: risk-area criteria first, then by lowest similarity.
    for g in gaps:
        g["risk"] = _is_risk(g["text"], risk_areas)
    # WHY: `not g["risk"]` sorts risk gaps (False) ahead of non-risk (True); ties break on
    # ascending max_similarity so the weakest-covered criteria come first.
    gaps.sort(key=lambda g: (not g["risk"], g["max_similarity"]))

    # WHY: baseline coverage with no removals — the starting point the floor gate later
    # compares change sets against.
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
