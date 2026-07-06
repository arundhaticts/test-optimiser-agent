"""
Duplicate / near-duplicate clustering (for redundancy detection).

cluster_duplicates groups tests whose text is semantically close above
DUPLICATE_THRESHOLD — catching duplicates that differ in wording but test the same
thing. Greedy single-linkage clustering on the similarity from nlp/similarity (which
uses real embeddings when available, else deterministic lexical overlap). scikit-learn
agglomerative clustering can drop in later without changing the interface.

Architecture position:
    nlp/ deterministic text backbone with offline fallbacks. Redundancy grouping
    built on the shared similarity primitive.

Called by:  nodes/redundancy.
Data in:    a list of test dicts.
Data out:   groups (lists) of near-duplicate test ids, each with >=2 members.
"""

from src.config import DUPLICATE_THRESHOLD
from src.nlp.similarity import semantic_sim, test_text


def cluster_duplicates(tests: list[dict], threshold: float = DUPLICATE_THRESHOLD) -> list[list[str]]:
    """Return groups (>=2 members) of near-duplicate test ids.

    Purpose:      group near-duplicate tests so redundancy can flag merges.
    Inputs:       tests list and a duplicate-similarity threshold.
    Outputs:      list of clusters (each a list of >=2 test ids).
    Side effects: None (pure).
    Called by:    nodes/redundancy.
    Calls:        similarity.semantic_sim, similarity.test_text.
    """
    # WHY: precompute the comparable text per id once so we don't rebuild it per pair.
    texts = {t["id"]: test_text(t) for t in tests}
    ids = list(texts)
    clusters: list[list[str]] = []
    # WHY: greedy single-linkage — walk each test and try to place it in an existing
    # cluster before starting a new one.
    for tid in ids:
        placed = False
        for cluster in clusters:
            # single-linkage: join if similar to ANY member
            # WHY: single-linkage join condition — one member above threshold is
            # enough to merge, chaining transitively-similar tests together.
            if any(semantic_sim(texts[tid], texts[other]) >= threshold for other in cluster):
                cluster.append(tid)
                placed = True
                break
        # WHY: no cluster accepted it -> seed a fresh singleton cluster.
        if not placed:
            clusters.append([tid])
    # WHY: singletons aren't redundancy — keep only clusters with >=2 members.
    return [c for c in clusters if len(c) >= 2]
