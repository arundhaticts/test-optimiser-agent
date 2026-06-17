"""
Embedding model wrapper (sentence-transformers) with an offline fallback.

load_embedder() loads the model named in EMBEDDING_MODEL once and reuses it. If
sentence-transformers isn't installed (offline demo), embed() falls back to a
deterministic hashing bag-of-words vector so cosine / nearest-neighbour still work
with no model download. The shared numeric backbone every semantic step builds on.
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
    """
    global _embedder
    if _embedder is None:
        if not USE_ST_EMBEDDINGS:
            _embedder = False
            return None
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
        except Exception:  # noqa: BLE001 — not installed / offline
            _embedder = False
    return _embedder or None


def _hash_vector(text: str) -> list[float]:
    """Deterministic L2-normalised bag-of-words vector (offline fallback)."""
    vec = [0.0] * _DIM
    for tok in normalise(text):
        # stable hash (Python's str hash is salted per process)
        h = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little")
        vec[h % _DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts into vectors (real model if present, else hashing)."""
    model = load_embedder()
    if model is not None:
        return [list(v) for v in model.encode(list(texts))]
    return [_hash_vector(t) for t in texts]


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def nearest_neighbours(query_vec, corpus_vecs, k: int = 5) -> list[tuple[int, float]]:
    """Return [(index, score)] of the k most similar corpus vectors, ranked."""
    scored = [(i, cosine(query_vec, v)) for i, v in enumerate(corpus_vecs)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
