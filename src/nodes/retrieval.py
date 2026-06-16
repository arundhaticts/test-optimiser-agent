"""
Node 4 — Context Retrieval (RAG).

MUST CONTAIN:
- retrieval_node(state) -> dict.
- Dense embedding retrieval over the vector store (tools/vector_store) for design
  docs, prior optimisation decisions, recent incidents.
- Load prior decisions from memory/store so rejected suggestions aren't repeated.
- Write 'retrieved_context' with source + extract + relevance score.
- Degrade path: empty retrieval is OK; note 'context thin'.
"""
