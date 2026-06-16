"""
Test-management / issue-tracker connector (Jira, Xray, TestRail, etc.).

MUST CONTAIN:
- get_acceptance_criteria(project_id) -> list of {id, text}: the criteria the suite
  is matched against in Node 2. For the prototype, read sample_data/sample_criteria.json
  (these would otherwise come from the User Story Analyser / Jira).
- get_known_issues(project_id) -> optional context for flakiness triage (e.g. tests
  already linked to open bugs). Used by retrieval/redundancy if available.
Fatal-tolerant: if the connector is unavailable, degrade to the fixture/empty set and
append to tool_errors rather than crashing (Blocker #3). Pairs with tools/repo_reader.
"""
