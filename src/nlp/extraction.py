"""
Classic NLP: tokenise / lemmatise / NER / keyword + log-pattern extraction.

Deterministic, no per-item LLM cost; used by intake (entities a test touches) and
flakiness triage (classify failure logs). spaCy is used if installed; otherwise a
lightweight offline tokeniser/lemmatiser keeps everything running.
"""

import re

from src.config import USE_SPACY

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "within",
    "is", "are", "be", "can", "should", "must", "that", "this", "it", "as", "by",
    "test", "tests", "case", "when", "then", "given", "valid", "via",
}

# Keyword signals that a CI failure is environmental (flaky) rather than a real defect.
_FLAKY_SIGNALS = (
    "timeout", "timed out", "connection", "connection reset", "retry", "retries",
    "race", "intermittent", "flaky", "socket", "temporarily", "deadline", "503", "502",
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _lemmatise(token: str) -> str:
    """Naive lemmatiser: strip a few common suffixes so plurals/tenses align."""
    for suf in ("ication", "ing", "ies", "ed", "es", "s"):
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)] + ("y" if suf == "ies" else "")
    return token


def normalise(text: str) -> list[str]:
    """Tokenise + drop stopwords + lemmatise. Returns a token list."""
    return [_lemmatise(t) for t in _tokens(text) if t not in _STOPWORDS]


def extract_entities(text: str) -> list[str]:
    """Entities a test references (endpoint/module/function-ish keywords).

    Uses spaCy NER if available; otherwise returns the deterministic normalised
    keyword set (good enough to link tests to code/criteria offline).
    """
    try:  # optional: richer entities when spaCy is enabled and installed
        nlp = _load_spacy()
        if nlp is not None:
            doc = nlp(text)
            ents = [e.text.lower() for e in doc.ents]
            if ents:
                return sorted(set(ents))
    except Exception:  # noqa: BLE001 — spaCy absent or model missing -> fallback
        pass
    return sorted(set(normalise(text)))


_spacy_nlp = None


def _load_spacy():
    """Load spaCy NER once; return None unless SPACY_NER=1 (skips the heavy import)."""
    global _spacy_nlp
    if _spacy_nlp is None:
        if not USE_SPACY:
            _spacy_nlp = False
            return None
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:  # noqa: BLE001
            _spacy_nlp = False
    return _spacy_nlp or None


def classify_failure_logs(logs: list[str]) -> dict:
    """Label failure logs 'flaky' (environmental) vs 'real' via keyword signals.

    Deterministic and cheap — no LLM call per failure. Returns a summary the
    redundancy node folds into its flakiness flags.
    """
    labels = []
    for line in logs or []:
        low = line.lower()
        labels.append("flaky" if any(sig in low for sig in _FLAKY_SIGNALS) else "real")
    return {
        "labels": labels,
        "flaky": labels.count("flaky"),
        "real": labels.count("real"),
        "total": len(labels),
    }
