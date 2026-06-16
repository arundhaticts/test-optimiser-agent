"""
All tunable constants in one place (no magic numbers scattered in nodes).

MUST CONTAIN:
- MAX_GEN_RETRIES = 3                 # bounds the validation loop
- DEFAULT_COVERAGE_TARGET = 0.80
- Similarity thresholds: CRITERIA_MATCH_THRESHOLD, DUPLICATE_THRESHOLD, GAP_THRESHOLD
- Flakiness/slow thresholds: FLAKY_FAIL_RATE, SLOW_TEST_SECONDS
- Tool retry settings: TOOL_RETRIES, BACKOFF_BASE
- Model names pulled from env (reasoning vs fast vs embedding).
Quantifies 'flaky', 'slow', 'redundant', and the score floor so they're not vibes.
"""
