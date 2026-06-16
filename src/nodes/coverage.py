"""
Node 2 — Coverage & Gap Analysis.

MUST CONTAIN:
- coverage_node(state) -> dict.
- Match each test to the acceptance criterion it satisfies using SEMANTIC
  SIMILARITY (nlp/similarity): embed test + criterion, cosine, threshold to link.
- Detect gaps via nearest-neighbour search: criteria/paths with low max-similarity.
- Rank gaps by risk (risk_areas weighted up).
- Write 'coverage_map' and 'coverage_gaps'.
- Degrade path: if no coverage report, fall back to static estimate, mark low-confidence.
"""
