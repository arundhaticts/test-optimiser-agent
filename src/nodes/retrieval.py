"""
Node 4 — Context Retrieval (RAG).

Embeds criteria + prior decisions into the vector store and retrieves context relevant
to the run (design notes, prior optimisation decisions). Also loads prior decisions and
protected tests from long-term memory so rejected suggestions aren't repeated. Empty
retrieval is fine — we just note 'context thin'.
"""

from src.observability import audit
from src.tools import vector_store, test_management
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.memory import store as memory


def retrieval_node(state) -> dict:
    project_id = state.get("project_id")
    suite = state.get("normalised_suite", [])

    # Seed the store with criteria so retrieval has something to match against.
    res = call_tool(test_management.get_acceptance_criteria, project_id)
    criteria = res["data"] if res["ok"] else []
    for c in criteria:
        vector_store.upsert(c["id"], c["text"], {"type": "criterion"})

    prior = memory.get_prior_decisions(project_id)
    protected = memory.get_protected_tests(project_id)
    for i, d in enumerate(prior):
        vector_store.upsert(f"decision:{i}", json_brief(d), {"type": "prior_decision"})

    # Retrieve context relevant to the suite's subject matter.
    query = " ".join(t.get("name", "") for t in suite) or "test suite optimisation"
    hits = vector_store.query(query, k=5)
    retrieved = [
        {"source": h["metadata"].get("type", "context"), "extract": h["text"],
         "relevance": round(h["score"], 3)}
        for h in hits
    ]

    errors = [] if res["ok"] else [tool_error_entry(
        "vector_store/retrieval", res["error"], "context thin")]

    return {
        "retrieved_context": retrieved,
        "approved_priority": state.get("approved_priority", {}),
        "tool_errors": errors,
        "audit_log": [audit("retrieval", "retrieved",
                            hits=len(retrieved), prior_decisions=len(prior),
                            protected=len(protected),
                            thin=len(retrieved) == 0)],
    }


def json_brief(d: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in d.items())
