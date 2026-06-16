"""
Node 1 — Intake & Normalise.

MUST CONTAIN:
- A function intake_node(state) -> dict (state updates).
- Parse heterogeneous test files via tools/test_parser into one internal shape.
- Run the NLP extraction (nlp/extraction): tokenise/lemmatise/NER to pull out the
  entities each test touches (endpoint, module, function).
- Write 'normalised_suite'. Isolate (don't drop) unparseable tests and log them.
Uses the FAST model only if needed; mostly deterministic parsing + NLP.
"""
