"""
Node 4 — Context Retrieval (RAG).

Embeds criteria + prior decisions into the vector store and retrieves context relevant
to the run (design notes, prior optimisation decisions). Also loads prior decisions and
protected tests from long-term memory so rejected suggestions aren't repeated. Empty
retrieval is fine — we just note 'context thin'.

Architecture position: Node 4 of 10 — Context Retrieval (RAG); runs after redundancy,
before scoring.
Called by: the graph (src/graph.py).
Data in: project_id, normalised_suite, approved_priority.
Data out: retrieved_context, approved_priority, tool_errors[+], audit_log[+].
"""

from src.observability import audit
from src.tools import vector_store, test_management
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.memory import store as memory


def retrieval_node(state) -> dict:
    """Seed the vector store and retrieve context relevant to the suite (RAG).

    Purpose: embed acceptance criteria + prior decisions into the vector store, load
        prior decisions/protected tests from long-term memory, then query for context
        relevant to the suite.
    Inputs: state — reads project_id, normalised_suite, approved_priority.
    Outputs: dict with retrieved_context, approved_priority (carried through),
        tool_errors[+], audit_log[+].
    Side effects: tool call via call_tool(get_acceptance_criteria); vector_store upsert
        and query; memory reads (get_prior_decisions, get_protected_tests); appends an
        audit log entry.
    Called by: the graph (src/graph.py).
    Calls: call_tool, test_management.get_acceptance_criteria, vector_store.upsert/query,
        memory.get_prior_decisions, memory.get_protected_tests, json_brief,
        tool_error_entry, audit.
    """
    project_id = state.get("project_id")
    suite = state.get("normalised_suite", [])

    # WHY: seed the vector store with criteria first so a query has something to match
    # against; degrade to empty criteria if the connector is unavailable.
    # Seed the store with criteria so retrieval has something to match against.
    res = call_tool(test_management.get_acceptance_criteria, project_id)
    criteria = res["data"] if res["ok"] else []
    for c in criteria:
        vector_store.upsert(c["id"], c["text"], {"type": "criterion"})

    # WHY: load long-term memory (prior decisions + protected tests) and seed prior
    # decisions too, so past choices inform retrieval and aren't re-suggested.
    prior = memory.get_prior_decisions(project_id)
    protected = memory.get_protected_tests(project_id)
    for i, d in enumerate(prior):
        vector_store.upsert(f"decision:{i}", json_brief(d), {"type": "prior_decision"})

    # WHY: build the query from the suite's test names (fallback to a generic phrase) and
    # pull the top-k most relevant seeded items as context.
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
    """Flatten a decision dict into a short "k=v k=v" string for embedding.

    Purpose: turn a prior-decision dict into a compact text form the vector store can
        embed and match against.
    Inputs: d (a decision dict).
    Outputs: a space-joined "key=value" string.
    Side effects: None (pure).
    Called by: retrieval_node.
    Calls: (none).
    """
    return " ".join(f"{k}={v}" for k, v in d.items())
