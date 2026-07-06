"""
Semantic Textual Similarity helpers (for coverage matching + gap detection).

Returns numeric confidence, not LLM guesses. Uses sentence-transformers cosine when a
real embedder is available; otherwise a deterministic lexical overlap so the offline
demo is reproducible. match_tests_to_criteria links tests to the criteria they satisfy;
find_gaps surfaces criteria no test covers.

Architecture position:
    nlp/ deterministic text backbone with offline fallbacks. This module is the
    shared similarity primitive layered on top of embeddings.

Called by:
    nodes/coverage (match_tests_to_criteria + find_gaps) and clustering
    (semantic_sim + test_text).

Data in:  test dicts and acceptance-criteria dicts.
Data out: [0, 1] similarity scores, a coverage_map/links dict, and gap lists.
"""

from src.config import CRITERIA_MATCH_THRESHOLD, GAP_THRESHOLD
from src.nlp.embeddings import load_embedder, embed, cosine
from src.nlp.extraction import normalise


def test_text(test: dict) -> str:
    """Human-readable text for a test: de-snaked name + docstring.

    Purpose:      build the comparable text blob for a test (name + docstring).
    Inputs:       a test dict (name/id/docstring).
    Outputs:      a single normalised-for-reading string.
    Side effects: None (pure).
    Called by:    match_tests_to_criteria, find_gaps, clustering.cluster_duplicates.
    Calls:        (dict access / str methods only).
    """
    name = test.get("name", test.get("id", ""))
    # WHY: strip the test_ prefix and un-snake so "test_login_ok" -> "login ok".
    name = name.replace("test_", "", 1).replace("_", " ")
    return f"{name} {test.get('docstring', '')}".strip()


def _token_match(x: str, y: str) -> bool:
    """True if two tokens match exactly or as a >=3-char substring of each other.

    Purpose:      fuzzy token equality for the lexical fallback.
    Inputs:       two token strings x, y.
    Outputs:      bool.
    Side effects: None (pure).
    Called by:    lexical_sim.
    Calls:        (str ops only).
    """
    # WHY: exact match, or substring containment for tokens long enough (>=3) to
    # avoid spurious matches on tiny fragments (catches stem/plural variants).
    return x == y or (len(x) >= 3 and len(y) >= 3 and (x in y or y in x))


def lexical_sim(a: str, b: str) -> float:
    """Deterministic token-overlap similarity in [0, 1] (offline backbone).

    Purpose:      similarity with no model — token overlap between two strings.
    Inputs:       two text strings a, b.
    Outputs:      overlap fraction in [0, 1].
    Side effects: None (pure).
    Called by:    semantic_sim (offline branch).
    Calls:        extraction.normalise, _token_match.
    """
    at, bt = set(normalise(a)), set(normalise(b))
    # WHY: empty token set on either side means no meaningful overlap.
    if not at or not bt:
        return 0.0
    # WHY: count matches from each side; asymmetric because containment is directional.
    matches_a = sum(1 for x in at if any(_token_match(x, y) for y in bt))
    matches_b = sum(1 for y in bt if any(_token_match(y, x) for x in at))
    # WHY: take the more generous side so a short criterion fully inside a long test
    # docstring still scores high.
    return max(matches_a / len(at), matches_b / len(bt))


def semantic_sim(a: str, b: str) -> float:
    """Cosine over real embeddings if available, else lexical overlap.

    Purpose:      the single similarity entry point used across the NLP layer.
    Inputs:       two text strings a, b.
    Outputs:      similarity float in [0, 1].
    Side effects: None (pure); may trigger a one-time model load.
    Called by:    match_tests_to_criteria, find_gaps, clustering.cluster_duplicates.
    Calls:        embeddings.load_embedder / embed / cosine, or lexical_sim.
    """
    # WHY: prefer semantic cosine when a real embedder exists; otherwise fall back
    # to deterministic lexical overlap so offline results stay reproducible.
    if load_embedder() is not None:
        va, vb = embed([a, b])
        return cosine(va, vb)
    return lexical_sim(a, b)


def match_tests_to_criteria(tests: list[dict], criteria: list[dict],
                            threshold: float = CRITERIA_MATCH_THRESHOLD) -> dict:
    """Link each test to the criteria it satisfies.

    Returns {coverage_map: {criterion_id: [test_id...]}, links: [{...confidence}]}.

    Purpose:      build the criterion -> covering-tests map used by coverage.
    Inputs:       tests list, criteria list, and a match threshold.
    Outputs:      {"coverage_map": {...}, "links": [{criterion_id, test_id, confidence}]}.
    Side effects: None (pure).
    Called by:    nodes/coverage.
    Calls:        semantic_sim, test_text.
    """
    # WHY: seed every criterion with an empty list so uncovered ones still appear.
    coverage_map: dict[str, list[str]] = {c["id"]: [] for c in criteria}
    links = []
    for c in criteria:
        for t in tests:
            # WHY: score each (criterion, test) pair; only keep pairs at/above the
            # match threshold as genuine coverage links.
            score = semantic_sim(c["text"], test_text(t))
            if score >= threshold:
                coverage_map[c["id"]].append(t["id"])
                links.append({"criterion_id": c["id"], "test_id": t["id"],
                              "confidence": round(score, 3)})
    return {"coverage_map": coverage_map, "links": links}


def find_gaps(criteria: list[dict], tests: list[dict],
              gap_threshold: float = GAP_THRESHOLD) -> list[dict]:
    """Criteria whose best matching test is below the gap threshold.

    Purpose:      surface acceptance criteria that no test adequately covers.
    Inputs:       criteria list, tests list, and a gap threshold.
    Outputs:      list of {criterion_id, text, max_similarity} for uncovered criteria.
    Side effects: None (pure).
    Called by:    nodes/coverage.
    Calls:        semantic_sim, test_text.
    """
    gaps = []
    for c in criteria:
        # WHY: a criterion is a gap only if even its BEST-matching test falls short,
        # so compare the max similarity across all tests against the gap threshold.
        best = max((semantic_sim(c["text"], test_text(t)) for t in tests), default=0.0)
        if best < gap_threshold:
            gaps.append({"criterion_id": c["id"], "text": c["text"],
                         "max_similarity": round(best, 3)})
    return gaps
