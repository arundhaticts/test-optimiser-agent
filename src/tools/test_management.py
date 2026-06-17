"""
Test-management / issue-tracker connector (Jira, Xray, TestRail, etc.).

get_acceptance_criteria(project_id) -> [{id, text}] the suite is matched against in
Node 2. For the prototype it reads sample_data/sample_criteria.json (these would
otherwise come from the User Story Analyser / Jira). get_known_issues is optional
context for flakiness triage. Connector-unavailable degrades to the fixture/empty
set rather than crashing (Blocker #3).
"""

import json
from pathlib import Path

_CRITERIA_FILE = Path(__file__).resolve().parents[2] / "sample_data" / "sample_criteria.json"


def get_acceptance_criteria(project_id: str | None = None) -> list[dict]:
    """Return acceptance criteria [{id, text}]. Empty list if unavailable."""
    if not _CRITERIA_FILE.exists():
        return []
    data = json.loads(_CRITERIA_FILE.read_text(encoding="utf-8"))
    return data.get("criteria", [])


def get_known_issues(project_id: str | None = None) -> list[dict]:
    """Tests already linked to open bugs. Empty for the prototype fixture."""
    return []
