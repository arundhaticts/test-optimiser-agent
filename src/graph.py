"""
Assembles the LangGraph: registers nodes, wires edges, sets routing, compiles.

This is the architecture made executable — it mirrors the Mermaid diagram in the spec:

    intake -> coverage -> redundancy -> retrieval -> scoring
      -> HITL 1 (approve removals)
      -> prioritisation -> [coverage-floor gate] <-> revise -> HITL 2 (approve ranking)
      -> gap_gen -> validation <-> (retry <=3) -> drop_failing -> HITL 3 (approve tests)
      -> assemble -> report -> END

The two conditional loops are the spec's Blocker fixes: the coverage-floor gate (#2)
blocks any removal set below target, and route_after_validation (#1) caps the
gap_gen/validation loop at MAX_GEN_RETRIES. A checkpointer persists state so the 3
interrupt() checkpoints can pause and resume.

Architecture position: wiring layer — turns the node functions into a compiled
    LangGraph state machine over TestOptimiserState. Owns no analysis logic itself.
Called by: main.run (CLI), api.py (HTTP), and the tests — each calls build_graph().
Data in: the imported node/router/HITL callables and TestOptimiserState schema;
    the CHECKPOINT_DB env var (read by make_checkpointer).
Data out: a compiled, runnable graph (with a checkpointer attached) that callers
    invoke; nodes then read/write TestOptimiserState as it flows through.
"""

import os

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.observability import get_logger
from src.state import TestOptimiserState
from src.nodes.intake import intake_node
from src.nodes.coverage import coverage_node
from src.nodes.redundancy import redundancy_node
from src.nodes.retrieval import retrieval_node
from src.nodes.scoring import scoring_node
from src.nodes.prioritisation import (
    prioritisation_node, coverage_floor_gate, revise_node,
)
from src.nodes.gap_generation import gap_generation_node
from src.nodes.validation import (
    validation_node, route_after_validation, drop_failing_node,
)
from src.nodes.assemble import assemble_node
from src.nodes.report import report_node
from src.hitl.interrupts import (
    hitl_removals_node, hitl_priority_node, hitl_generated_node,
)


_log = get_logger("graph")


def make_checkpointer():
    """Pick the checkpointer that backs interrupt()/resume.

    Default: in-memory `MemorySaver` — paused runs are lost on process restart. That's
    fine for the CLI and the demo. For real automation (API/webhook) set
    `CHECKPOINT_DB=<path.sqlite>` to persist paused/resumable runs across restarts
    (requires `pip install langgraph-checkpoint-sqlite`). If the env var is set but the
    package is unavailable, we log and fall back to in-memory rather than crash.

    Purpose: choose the persistence backend for the graph's checkpoints.
    Inputs: the CHECKPOINT_DB environment variable (path to a SQLite file, or unset).
    Outputs: a checkpointer instance (SqliteSaver when configured, else MemorySaver).
    Side effects: may open a SQLite connection; logs the chosen backend / any fallback.
    Called by: build_graph (when no checkpointer is passed in).
    Calls: os.getenv, sqlite3.connect, SqliteSaver, MemorySaver, _log.
    """
    # WHY: pick SqliteSaver only when CHECKPOINT_DB is set; else fall back to in-memory.
    # The import + connect is guarded so a missing optional package never blocks startup.
    db = os.getenv("CHECKPOINT_DB")
    if db:
        try:
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver

            conn = sqlite3.connect(db, check_same_thread=False)
            _log.info("checkpointer: SqliteSaver (persistent) | db=%s", db)
            return SqliteSaver(conn)
        except Exception as e:  # noqa: BLE001 — never block startup on the optional dep
            _log.warning("CHECKPOINT_DB set but SqliteSaver unavailable (%s) — falling back "
                         "to in-memory. Install: pip install langgraph-checkpoint-sqlite", e)
    return MemorySaver()


def build_graph(checkpointer=None):
    """Build and compile the Test Optimiser graph. A checkpointer is required for the
    interrupt()/resume checkpoints; one is created via make_checkpointer() if not supplied.

    Purpose: register every node, wire the edges/routing/loops, and compile the graph.
    Inputs: an optional checkpointer (defaults to make_checkpointer()'s choice).
    Outputs: a compiled LangGraph app ready to .invoke() over TestOptimiserState.
    Side effects: none beyond building the graph (checkpointer creation may open SQLite).
    Called by: main.run, api.py, and the tests.
    Calls: StateGraph, add_node / add_edge / add_conditional_edges, make_checkpointer,
        g.compile; references all node/router/HITL callables imported above.
    """
    g = StateGraph(TestOptimiserState)

    # WHY: register all 15 vertices first — the 10 work nodes plus the 2 auxiliary nodes
    # (revise, drop_failing) and the 3 HITL interrupt nodes — before any edges reference them.
    # --- 10 work nodes + 2 auxiliary nodes ---
    g.add_node("intake", intake_node)
    g.add_node("coverage", coverage_node)
    g.add_node("redundancy", redundancy_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("scoring", scoring_node)
    g.add_node("hitl_removals", hitl_removals_node)        # HITL 1
    g.add_node("prioritisation", prioritisation_node)
    g.add_node("revise", revise_node)                      # auxiliary (REVISE)
    g.add_node("hitl_priority", hitl_priority_node)        # HITL 2
    g.add_node("gap_gen", gap_generation_node)
    g.add_node("validation", validation_node)
    g.add_node("drop_failing", drop_failing_node)          # auxiliary (DROPGEN)
    g.add_node("hitl_generated", hitl_generated_node)      # HITL 3
    g.add_node("assemble", assemble_node)
    g.add_node("report", report_node)

    # WHY: the fixed analysis spine — one unconditional edge per hop, START through the
    # first HITL checkpoint into prioritisation, matching the spec diagram's linear phase.
    # --- Linear analysis spine ---
    g.add_edge(START, "intake")
    g.add_edge("intake", "coverage")
    g.add_edge("coverage", "redundancy")
    g.add_edge("redundancy", "retrieval")
    g.add_edge("retrieval", "scoring")
    g.add_edge("scoring", "hitl_removals")
    g.add_edge("hitl_removals", "prioritisation")

    # WHY: form the coverage-floor loop (Blocker #2). The gate runs after BOTH prioritisation
    # and revise, so each revise iteration is re-checked: below target -> "revise" (loop back),
    # at/above target -> "approve_ranking" (exit to HITL 2). Same routing map on both edges
    # closes the revise -> gate -> revise cycle; revise_count caps it at MAX_REVISE_ITERS.
    # --- Coverage-floor gate (Blocker #2): prioritisation -> gate <-> revise -> HITL2 ---
    g.add_conditional_edges("prioritisation", coverage_floor_gate,
                            {"revise": "revise", "approve_ranking": "hitl_priority"})
    g.add_conditional_edges("revise", coverage_floor_gate,
                            {"revise": "revise", "approve_ranking": "hitl_priority"})

    g.add_edge("hitl_priority", "gap_gen")
    g.add_edge("gap_gen", "validation")

    # WHY: form the bounded generation loop (Blocker #1). route_after_validation decides,
    # after validation: "approve_tests" (valid -> HITL 3), "gap_gen" (invalid, retries left ->
    # regenerate; gen_retry_count climbs), or "drop_failing" (retries exhausted -> proceed
    # without the failing drafts). drop_failing then rejoins the linear path at HITL 3.
    # --- Bounded validation loop (Blocker #1) ---
    g.add_conditional_edges("validation", route_after_validation,
                            {"approve_tests": "hitl_generated",
                             "gap_gen": "gap_gen",
                             "drop_failing": "drop_failing"})
    g.add_edge("drop_failing", "hitl_generated")

    # WHY: final linear tail — approved tests flow into assemble (builds the plan), then
    # report (renders the 4 deliverables + writes memory), then END.
    g.add_edge("hitl_generated", "assemble")
    g.add_edge("assemble", "report")
    g.add_edge("report", END)

    # WHY: compile with a checkpointer (caller-supplied or the make_checkpointer() default)
    # — required so the 3 interrupt() checkpoints can persist state and later resume.
    return g.compile(checkpointer=checkpointer or make_checkpointer())
