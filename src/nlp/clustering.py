"""
Duplicate / near-duplicate clustering (for redundancy detection).

MUST CONTAIN:
- cluster_duplicates(test_vectors, threshold) -> groups of semantically similar tests
  (e.g. agglomerative clustering on cosine distance, scikit-learn).
Catches duplicates that differ in wording but test the same thing.
"""
