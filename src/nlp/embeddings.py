"""
Embedding model wrapper (sentence-transformers) with an offline fallback.

load_embedder() loads the model named in EMBEDDING_MODEL once and reuses it. If
sentence-transformers isn't installed (offline demo), embed() falls back to a
deterministic hashing bag-of-words vector so cosine / nearest-neighbour still work
with no model download. The shared numeric backbone every semantic step builds on.

Architecture position:
    nlp/ deterministic text backbone with offline fallbacks. This module is the
    numeric root: everything semantic (similarity, clustering, vector search)
    reduces to vectors + cosine produced here.

Called by:
    similarity.semantic_sim and tools/vector_store (both via embed / cosine).

Data in:  lists of raw text strings.
Data out: float vectors and [0, 1] cosine / nearest-neighbour scores.
"""

import hashlib
import math

from src.config import EMBEDDING_MODEL, USE_ST_EMBEDDINGS
from src.nlp.extraction import normalise

_DIM = 256          # fallback hashing-vector dimensionality
_embedder = None    # cached real model (or False if unavailable)


def load_embedder():
    """Load the sentence-transformers model once; return None if unavailable.

    When real embeddings aren't explicitly enabled (EMBED_ALLOW_DOWNLOAD=1) we skip the
    import entirely — sentence-transformers pulls in PyTorch, a multi-minute import on
    some machines — and use the deterministic hashing fallback instead.

    Purpose:      lazily obtain (and cache) the real embedder, or signal its absence.
    Inputs:       none (reads USE_ST_EMBEDDINGS / EMBEDDING_MODEL from config).
    Outputs:      the SentenceTransformer instance, or None to trigger the fallback.
    Side effects: None (pure) beyond populating the module-level cache _embedder.
    Called by:    embed, similarity.semantic_sim.
    Calls:        sentence_transformers.SentenceTransformer (optional import).
    """
    global _embedder
    # WHY: offline path — flag off means never import ST; cache False so we never retry.
    if _embedder is None:
        if not USE_ST_EMBEDDINGS:
            _embedder = False
            return None
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
        except Exception:  # noqa: BLE001 — not installed / offline
            # WHY: any import/load failure degrades to the deterministic fallback.
            _embedder = False
    # WHY: _embedder is False (unavailable) -> None; a real model -> itself.
    return _embedder or None


def _hash_vector(text: str) -> list[float]:
    """Deterministic L2-normalised bag-of-words vector (offline fallback).

    Purpose:      turn text into a stable vector when no real embedder is present.
    Inputs:       a single text string.
    Outputs:      an L2-normalised list[float] of length _DIM.
    Side effects: None (pure).
    Called by:    embed (offline branch only).
    Calls:        extraction.normalise, hashlib.md5.
    """
    vec = [0.0] * _DIM
    # WHY: bucket each normalised token by a stable hash — Python's str hash is
    # salted per process, so md5 keeps vectors reproducible across runs.
    for tok in normalise(text):
        # stable hash (Python's str hash is salted per process)
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
        vec[h % _DIM] += 1.0
    # WHY: L2-normalise so cosine reduces to a plain dot product; guard div-by-zero.
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into vectors (real model if present, else hashing).

    Purpose:      convert texts to vectors, transparently choosing real vs fallback.
    Inputs:       a list of text strings.
    Outputs:      a list of float vectors (one per input).
    Side effects: None (pure); first call may trigger model load via load_embedder.
    Called by:    similarity.semantic_sim, tools/vector_store.
    Calls:        load_embedder, model.encode, _hash_vector.
    """
    model = load_embedder()
    # WHY: real embeddings when the model loaded; otherwise deterministic hash vectors.
    if model is not None:
        return [list(v) for v in model.encode(list(texts))]
    return [_hash_vector(t) for t in texts]


def cosine(a, b) -> float:
    """Cosine similarity between two vectors, in [0, 1] for these vectors.

    Purpose:      shared similarity primitive over embedding vectors.
    Inputs:       two equal-length numeric sequences a, b.
    Outputs:      cosine similarity float (0.0 when either vector is zero-length).
    Side effects: None (pure).
    Called by:    similarity.semantic_sim, nearest_neighbours, vector_store.query.
    Calls:        (stdlib math only).
    """
    # WHY: cosine = dot(a, b) / (|a| * |b|); compute dot and both magnitudes.
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    # WHY: guard the zero-vector case so we never divide by zero.
    return dot / (na * nb) if na and nb else 0.0


def nearest_neighbours(query_vec, corpus_vecs, k: int = 5) -> list[tuple[int, float]]:
    """Return [(index, score)] of the k most similar corpus vectors, ranked.

    Purpose:      top-k nearest-neighbour search over a corpus of vectors.
    Inputs:       query_vec, corpus_vecs (list of vectors), k (how many to return).
    Outputs:      list of (corpus_index, cosine_score) sorted best-first, truncated to k.
    Side effects: None (pure).
    Called by:    utility helper (retrieval-style callers).
    Calls:        cosine.
    """
    # WHY: score every corpus vector against the query, keeping its original index.
    scored = [(i, cosine(query_vec, v)) for i, v in enumerate(corpus_vecs)]
    # WHY: rank most-similar first, then keep only the top k.
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
