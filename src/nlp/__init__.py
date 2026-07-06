"""NLP layer: embeddings, similarity, clustering, text extraction.

The deterministic text backbone of the agent, with offline fallbacks so every
semantic step runs with no model download and no network.

Architecture position:
    nlp/ = deterministic text backbone with offline fallbacks. It provides the
    numeric/text primitives (embeddings, cosine, similarity, clustering, entity
    and log extraction) that the graph nodes build coverage/redundancy analysis
    on. LLM judgement lives elsewhere; this layer is pure, reproducible NLP.

Called by:
    - embeddings   <- similarity + tools/vector_store
    - similarity   <- nodes/coverage + clustering
    - clustering   <- nodes/redundancy
    - extraction   <- nodes/intake + embeddings (hash-vector normalisation)

Data in:
    Raw test dicts, acceptance-criteria text, and free text (docstrings, logs).

Data out:
    Numeric vectors, [0, 1] similarity scores, coverage maps, gap lists,
    duplicate clusters, and normalised token/entity lists.
"""
