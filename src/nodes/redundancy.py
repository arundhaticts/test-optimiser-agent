"""
Node 3 — Redundancy & Flakiness Detection.

MUST CONTAIN:
- redundancy_node(state) -> dict.
- Duplicate detection: embedding similarity + cosine threshold + CLUSTERING
  (nlp/clustering) to group semantic near-duplicates.
- Flakiness/slow triage: pull CI history (tools/ci_history); apply FLAKY_FAIL_RATE
  and SLOW_TEST_SECONDS thresholds; classify failure logs (nlp/extraction + TF-IDF).
- Write 'redundancy_flags' and 'flakiness_flags', each WITH evidence.
- Degrade path: insufficient history -> flag 'needs more data', don't assert.
"""
