"""
Semantic Textual Similarity helpers (for coverage matching + gap detection).

Returns numeric confidence, not LLM guesses. Uses sentence-transformers cosine when a
real embedder is available; otherwise a deterministic lexical overlap so the offline
demo is reproducible. match_tests_to_criteria links tests to the criteria they satisfy;
find_gaps surfaces criteria no test covers.
"""

from src.config import CRITERIA_MATCH_THRESHOLD, GAP_THRESHOLD
from src.nlp.embeddings import load_embedder, embed, cosine
from src.nlp.extraction import normalise


def test_text(test: dict) -> str:
    """Human-readable text for a test: de-snaked name + docstring."""
    name = test.get("name", test.get("id", ""))
    name = name.replace("test_", "", 1).replace("_", " ")
    return f"{name} {test.get('docstring', '')}".strip()


def _token_match(x: str, y: str) -> bool:
    return x == y or (len(x) >= 3 and len(y) >= 3 and (x in y or y in x))


def lexical_sim(a: str, b: str) -> float:
    """Deterministic token-overlap similarity in [0, 1] (offline backbone)."""
    at, bt = set(normalise(a)), set(normalise(b))
    if not at or not bt:
        return 0.0
    matches_a = sum(1 for x in at if any(_token_match(x, y) for y in bt))
    matches_b = sum(1 for y in bt if any(_token_match(y, x) for x in at))
    return max(matches_a / len(at), matches_b / len(bt))


def semantic_sim(a: str, b: str) -> float:
    """Cosine over real embeddings if available, else lexical overlap."""
    if load_embedder() is not None:
        va, vb = embed([a, b])
        return cosine(va, vb)
    return lexical_sim(a, b)


def match_tests_to_criteria(tests: list[dict], criteria: list[dict],
                            threshold: float = CRITERIA_MATCH_THRESHOLD) -> dict:
    """Link each test to the criteria it satisfies.

    Returns {coverage_map: {criterion_id: [test_id...]}, links: [{...confidence}]}.
    """
    coverage_map: dict[str, list[str]] = {c["id"]: [] for c in criteria}
    links = []
    for c in criteria:
        for t in tests:
            score = semantic_sim(c["text"], test_text(t))
            if score >= threshold:
                coverage_map[c["id"]].append(t["id"])
                links.append({"criterion_id": c["id"], "test_id": t["id"],
                              "confidence": round(score, 3)})
    return {"coverage_map": coverage_map, "links": links}


def find_gaps(criteria: list[dict], tests: list[dict],
              gap_threshold: float = GAP_THRESHOLD) -> list[dict]:
    """Criteria whose best matching test is below the gap threshold."""
    gaps = []
    for c in criteria:
        best = max((semantic_sim(c["text"], test_text(t)) for t in tests), default=0.0)
        if best < gap_threshold:
            gaps.append({"criterion_id": c["id"], "text": c["text"],
                         "max_similarity": round(best, 3)})
    return gaps
