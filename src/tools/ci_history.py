"""
Historical CI-run datastore access (mocked for the prototype).

MUST CONTAIN:
- get_history(test_id) -> pass/fail variance + execution times, used for flakiness
  and slow-test detection. For the prototype, read sample_data/mock_ci_history.json.
"""
