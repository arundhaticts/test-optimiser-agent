"""
Long-term, per-project store (the Phase 5 feedback loop).

MUST CONTAIN:
- save_decision(project_id, decision): accepted/rejected recommendations.
- get_prior_decisions(project_id): so the agent never re-suggests a rejected change.
- record_flaky(project_id, test_id), get_protected_tests(project_id).
Separate from run state: this persists ACROSS runs, keyed by project.
"""
