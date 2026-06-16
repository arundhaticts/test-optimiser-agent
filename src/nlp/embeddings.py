"""
Embedding model wrapper (sentence-transformers).

MUST CONTAIN:
- load_embedder(): load the model named in EMBEDDING_MODEL once, reuse it.
- embed(texts) -> vectors.
- cosine(a, b) -> float.
- nearest_neighbours(query_vec, corpus_vecs, k) -> ranked matches.
The shared numeric backbone every semantic step builds on.
"""
