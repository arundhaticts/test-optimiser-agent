"""
Classic NLP: tokenise / lemmatise / NER / keyword + log-pattern extraction.

Deterministic, no per-item LLM cost; used by intake (entities a test touches) and
flakiness triage (classify failure logs). spaCy is used if installed; otherwise a
lightweight offline tokeniser/lemmatiser keeps everything running.

Architecture position:
    nlp/ deterministic text backbone with offline fallbacks. The lowest-level text
    normaliser; embeddings and similarity both reduce text to tokens via normalise.

Called by:
    nodes/intake (extract_entities) and embeddings._hash_vector / similarity
    (normalise).

Data in:  raw text (docstrings, test names) and CI failure-log lines.
Data out: normalised token lists, entity lists, and a flaky-vs-real log summary.
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
    """Lowercase alphanumeric tokeniser.

    Purpose:      split text into simple [a-z0-9]+ tokens.
    Inputs:       a text string (None tolerated).
    Outputs:      list of lowercase token strings.
    Side effects: None (pure).
    Called by:    normalise.
    Calls:        re.findall.
    """
    # WHY: lowercase + keep only alphanumeric runs; drops punctuation/whitespace.
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _lemmatise(token: str) -> str:
    """Naive lemmatiser: strip a few common suffixes so plurals/tenses align.

    Purpose:      collapse simple inflections so "logins"/"logging" align to a stem.
    Inputs:       a single token.
    Outputs:      the (possibly) de-suffixed token.
    Side effects: None (pure).
    Called by:    normalise.
    Calls:        (str ops only).
    """
    # WHY: try suffixes longest-first; only strip when a >=3-char stem remains so we
    # don't mangle short words. "ies" -> "y" (e.g. "queries" -> "query").
    for suf in ("ication", "ing", "ies", "ed", "es", "s"):
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)] + ("y" if suf == "ies" else "")
    return token


def normalise(text: str) -> list[str]:
    """Tokenise + drop stopwords + lemmatise. Returns a token list.

    Purpose:      the canonical text->token pipeline shared across the NLP layer.
    Inputs:       a text string.
    Outputs:      list of normalised tokens (stopwords removed, lemmatised).
    Side effects: None (pure).
    Called by:    similarity.lexical_sim, embeddings._hash_vector, extract_entities.
    Calls:        _tokens, _lemmatise.
    """
    # WHY: tokenise, drop noise stopwords, then lemmatise each survivor.
    return [_lemmatise(t) for t in _tokens(text) if t not in _STOPWORDS]


def extract_entities(text: str) -> list[str]:
    """Entities a test references (endpoint/module/function-ish keywords).

    Uses spaCy NER if available; otherwise returns the deterministic normalised
    keyword set (good enough to link tests to code/criteria offline).

    Purpose:      extract the entities/keywords a test touches for intake.
    Inputs:       raw text (test name + docstring).
    Outputs:      sorted, de-duplicated list of entity/keyword strings.
    Side effects: None (pure); may trigger a one-time spaCy load.
    Called by:    nodes/intake.
    Calls:        _load_spacy, normalise.
    """
    # WHY: prefer real NER when spaCy is enabled and yields entities...
    try:  # optional: richer entities when spaCy is enabled and installed
        nlp = _load_spacy()
        if nlp is not None:
            doc = nlp(text)
            ents = [e.text.lower() for e in doc.ents]
            # WHY: only use NER output if it actually found something.
            if ents:
                return sorted(set(ents))
    except Exception:  # noqa: BLE001 — spaCy absent or model missing -> fallback
        pass
    # WHY: fallback (and default) — the deterministic normalised keyword set.
    return sorted(set(normalise(text)))


_spacy_nlp = None


def _load_spacy():
    """Load spaCy NER once; return None unless SPACY_NER=1 (skips the heavy import).

    Purpose:      lazily obtain (and cache) the spaCy pipeline, or signal absence.
    Inputs:       none (reads USE_SPACY from config).
    Outputs:      the spaCy nlp object, or None to trigger the token fallback.
    Side effects: None (pure) beyond populating the module cache _spacy_nlp.
    Called by:    extract_entities.
    Calls:        spacy.load (optional import).
    """
    global _spacy_nlp
    # WHY: offline path — flag off means never import spaCy; cache False so we never retry.
    if _spacy_nlp is None:
        if not USE_SPACY:
            _spacy_nlp = False
            return None
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:  # noqa: BLE001
            # WHY: missing package or model degrades to the token fallback.
            _spacy_nlp = False
    # WHY: False (unavailable) -> None; a loaded pipeline -> itself.
    return _spacy_nlp or None


def classify_failure_logs(logs: list[str]) -> dict:
    """Label failure logs 'flaky' (environmental) vs 'real' via keyword signals.

    Deterministic and cheap — no LLM call per failure. Returns a summary the
    redundancy node folds into its flakiness flags.

    Purpose:      triage CI failure logs into flaky vs real by keyword signals.
    Inputs:       a list of failure-log lines.
    Outputs:      {labels, flaky, real, total} summary dict.
    Side effects: None (pure).
    Called by:    flakiness triage (available to nodes/redundancy).
    Calls:        (str ops only, against _FLAKY_SIGNALS).
    """
    labels = []
    # WHY: a line is "flaky" if it contains any environmental signal (timeout, reset,
    # 5xx, race, ...); anything else is treated as a "real" defect.
    for line in logs or []:
        low = line.lower()
        labels.append("flaky" if any(sig in low for sig in _FLAKY_SIGNALS) else "real")
    return {
        "labels": labels,
        "flaky": labels.count("flaky"),
        "real": labels.count("real"),
        "total": len(labels),
    }
