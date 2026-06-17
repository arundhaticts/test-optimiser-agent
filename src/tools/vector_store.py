"""
Vector store interface (in-memory for the prototype; swap for Chroma/FAISS later).

Holds embedded tests, criteria, docs, and prior decisions. upsert(id, text, metadata)
and query(text, k) back the RAG retrieval step and similarity work. Embeddings come
from src.nlp.embeddings, which has a deterministic offline fallback so this runs with
no model download.
"""


class VectorStore:
    def __init__(self):
        self._items: dict[str, dict] = {}   # id -> {text, metadata, vector}

    def upsert(self, id: str, text: str, metadata: dict | None = None) -> None:
        from src.nlp.embeddings import embed
        self._items[id] = {
            "text": text,
            "metadata": metadata or {},
            "vector": embed([text])[0],
        }

    def query(self, text: str, k: int = 5) -> list[dict]:
        """Return up to k nearest items: [{id, text, metadata, score}]."""
        from src.nlp.embeddings import embed, cosine
        if not self._items:
            return []
        qv = embed([text])[0]
        scored = [
            {"id": _id, "text": it["text"], "metadata": it["metadata"],
             "score": cosine(qv, it["vector"])}
            for _id, it in self._items.items()
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)


# Module-level default store for simple prototype use.
_default = VectorStore()


def upsert(id: str, text: str, metadata: dict | None = None) -> None:
    _default.upsert(id, text, metadata)


def query(text: str, k: int = 5) -> list[dict]:
    return _default.query(text, k)
