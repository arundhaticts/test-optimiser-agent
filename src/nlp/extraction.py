"""
Classic NLP: tokenise / lemmatise / NER / keyword + log-pattern extraction.

MUST CONTAIN:
- extract_entities(text) -> endpoints/modules/functions a test references (spaCy NER).
- normalise(text) -> tokenised + lemmatised form.
- classify_failure_logs(logs) -> structured 'flaky vs real' signals (TF-IDF/keywords).
Deterministic, no per-item LLM cost; used by intake + flakiness triage.
"""
