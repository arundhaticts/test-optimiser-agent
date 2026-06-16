"""
Semantic Textual Similarity helpers (for coverage matching + gap detection).

MUST CONTAIN:
- match_tests_to_criteria(tests, criteria, threshold) -> links with confidence.
- find_gaps(criteria, tests, gap_threshold) -> criteria with low max-similarity.
Built on nlp/embeddings; returns numeric confidence, not LLM guesses.
"""
