"""
Vector store interface (Chroma/FAISS for the prototype).

MUST CONTAIN:
- upsert(id, text, metadata), query(text, k) for RAG retrieval and similarity work.
- Holds embedded tests, criteria, docs, and prior decisions.
"""
