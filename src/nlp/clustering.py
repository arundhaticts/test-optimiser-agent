"""
Duplicate / near-duplicate clustering (for redundancy detection).

cluster_duplicates groups tests whose text is semantically close above
DUPLICATE_THRESHOLD — catching duplicates that differ in wording but test the same
thing. Greedy single-linkage clustering on the similarity from nlp/similarity (which
uses real embeddings when available, else deterministic lexical overlap). scikit-learn
agglomerative clustering can drop in later without changing the interface.
"""

from src.config import DUPLICATE_THRESHOLD
from src.nlp.similarity import semantic_sim, test_text


def cluster_duplicates(tests: list[dict], threshold: float = DUPLICATE_THRESHOLD) -> list[list[str]]:
    """Return groups (>=2 members) of near-duplicate test ids."""
    texts = {t["id"]: test_text(t) for t in tests}
    ids = list(texts)
    clusters: list[list[str]] = []
    for tid in ids:
        placed = False
        for cluster in clusters:
            # single-linkage: join if similar to ANY member
            if any(semantic_sim(texts[tid], texts[other]) >= threshold for other in cluster):
                cluster.append(tid)
                placed = True
                break
        if not placed:
            clusters.append([tid])
    return [c for c in clusters if len(c) >= 2]
