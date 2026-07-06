"""
Vector store interface (in-memory for the prototype; swap for Chroma/FAISS later).

Holds embedded tests, criteria, docs, and prior decisions. upsert(id, text, metadata)
and query(text, k) back the RAG retrieval step and similarity work. Embeddings come
from src.nlp.embeddings, which has a deterministic offline fallback so this runs with
no model download.

Architecture position:
    Integration layer (tools/). Backs the RAG retrieval step; embeddings are delegated
    to ``src.nlp.embeddings`` (real or hashed offline vectors).
Called by:
    module-level ``upsert`` / ``query`` <- retrieval_node (they wrap a singleton store).
Data in:   item id + text (+ metadata) on upsert; a query string + top-k on query.
Data out:  None on upsert; ranked hits ``[{id, text, metadata, score}]`` on query.
"""


class VectorStore:
    """
    Purpose:  in-memory embedded-item store backing similarity/RAG lookups.
    Inputs:   items via ``upsert``; query text via ``query``.
    Outputs:  ranked hit dicts from ``query``; item count from ``__len__``.
    Side effects: computes embeddings (via ``src.nlp.embeddings``) on upsert/query.
    Called by: the module-level ``upsert``/``query`` singleton wrappers.
    Calls:    ``embeddings.embed`` / ``embeddings.cosine``.
    """

    def __init__(self):
        """
        Purpose:  create an empty store.
        Inputs:   None.  Outputs: None.  Side effects: None (pure).
        Called by: module import (the ``_default`` singleton) / tests.  Calls: None.
        """
        self._items: dict[str, dict] = {}   # id -> {text, metadata, vector}

    def upsert(self, id: str, text: str, metadata: dict | None = None) -> None:
        """
        Purpose:  insert/replace one item, embedding its text at write time.
        Inputs:   ``id``, ``text``, optional ``metadata``.
        Outputs:  None.
        Side effects: computes an embedding (``embed``) and mutates ``self._items``.
        Called by: module-level ``upsert`` (<- retrieval_node).
        Calls:    ``embeddings.embed``.
        """
        from src.nlp.embeddings import embed
        # WHY: embed-on-upsert — store the vector alongside the text now so query() only
        # has to embed the query, not the whole corpus each time.
        self._items[id] = {
            "text": text,
            "metadata": metadata or {},
            "vector": embed([text])[0],
        }

    def query(self, text: str, k: int = 5) -> list[dict]:
        """
        Return up to k nearest items: [{id, text, metadata, score}].

        Purpose:  cosine-rank stored items against a query string.
        Inputs:   ``text`` query, ``k`` (max hits).
        Outputs:  up to ``k`` hit dicts sorted by descending score.
        Side effects: embeds the query (``embed``); no mutation.
        Called by: module-level ``query`` (<- retrieval_node).
        Calls:    ``embeddings.embed``, ``embeddings.cosine``.
        """
        from src.nlp.embeddings import embed, cosine
        # WHY: nothing stored yet -> no hits (avoids embedding a query for nothing).
        if not self._items:
            return []
        qv = embed([text])[0]
        # WHY: score every item by cosine similarity between the query vector and each
        # stored vector (higher = more similar).
        scored = [
            {"id": _id, "text": it["text"], "metadata": it["metadata"],
             "score": cosine(qv, it["vector"])}
            for _id, it in self._items.items()
        ]
        # WHY: sort by score descending and keep the top-k most similar items.
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        """
        Purpose:  report how many items are stored.
        Inputs:   None.  Outputs: item count (int).  Side effects: None (pure).
        Called by: callers/tests checking store size.  Calls: None.
        """
        return len(self._items)


# Module-level default store for simple prototype use.
# WHY: a process-wide singleton lets nodes call upsert/query without threading a store
# instance through the state.
_default = VectorStore()


def upsert(id: str, text: str, metadata: dict | None = None) -> None:
    """
    Purpose:  singleton wrapper — upsert into the module ``_default`` store.
    Inputs:   ``id``, ``text``, optional ``metadata``.
    Outputs:  None.
    Side effects: embeds text and mutates the default store.
    Called by: retrieval_node.
    Calls:    ``_default.upsert``.
    """
    _default.upsert(id, text, metadata)


def query(text: str, k: int = 5) -> list[dict]:
    """
    Purpose:  singleton wrapper — query the module ``_default`` store.
    Inputs:   ``text`` query, ``k`` (max hits).
    Outputs:  up to ``k`` ranked hit dicts.
    Side effects: embeds the query (no mutation).
    Called by: retrieval_node.
    Calls:    ``_default.query``.
    """
    return _default.query(text, k)
