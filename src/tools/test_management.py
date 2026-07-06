"""
Test-management / issue-tracker connector (Jira, Xray, TestRail, etc.).

get_acceptance_criteria(project_id) -> [{id, text}] the suite is matched against in
Node 2. For the prototype it reads sample_data/sample_criteria.json (these would
otherwise come from the User Story Analyser / Jira). get_known_issues is optional
context for flakiness triage. Connector-unavailable degrades to the fixture/empty
set rather than crashing (Blocker #3).

Architecture position:
    Integration layer (tools/). Reached via ``tool_wrapper.call_tool`` (Blocker #3);
    a missing fixture degrades to an empty list rather than raising.
Called by:
    ``get_acceptance_criteria`` <- coverage_node and retrieval_node (both via
    ``call_tool``); ``get_known_issues`` is reserved.
Data in:   the fixed fixture ``sample_data/sample_criteria.json`` (its ``"criteria"`` key).
Data out:  acceptance criteria ``[{id, text}]`` (or ``[]``); known issues ``[]``.
"""

import json
from pathlib import Path

_CRITERIA_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "sample_criteria.json"


def get_acceptance_criteria(project_id: str | None = None) -> list[dict]:
    """
    Return acceptance criteria [{id, text}]. Empty list if unavailable.

    Purpose:  supply the acceptance criteria the suite is matched against (Node 2).
    Inputs:   ``project_id`` (accepted for a real connector; unused by the fixture).
    Outputs:  ``[{id, text}]`` from the fixture, or ``[]`` if it's missing.
    Side effects: reads ``sample_data/sample_criteria.json`` from disk.
    Called by: coverage_node, retrieval_node (via ``call_tool``).
    Calls:    ``json.loads``, ``Path.read_text``.
    """
    # WHY: connector/fixture unavailable degrades to [] (Blocker #3) — the node then
    # continues with no criteria rather than crashing the run.
    if not _CRITERIA_FILE.exists():
        return []
    data = json.loads(_CRITERIA_FILE.read_text(encoding="utf-8"))
    # WHY: only the "criteria" array is the payload; default to [] if the key is absent.
    return data.get("criteria", [])


def get_known_issues(project_id: str | None = None) -> list[dict]:
    """
    Tests already linked to open bugs. Empty for the prototype fixture.

    Purpose:  reserved hook for flakiness-triage context (tests tied to open bugs).
    Inputs:   ``project_id`` (unused in the stub).
    Outputs:  ``[]`` (stub).
    Side effects: None (pure).
    Called by: reserved (not on the main spine).
    Calls:    None.
    """
    return []
