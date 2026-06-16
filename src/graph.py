"""
Assembles the LangGraph: registers nodes, wires edges, sets routing, compiles.

MUST CONTAIN:
- StateGraph(TestOptimiserState) construction.
- add_node() for all 10 nodes (imported from src/nodes/), PLUS the two auxiliary
  nodes from the diagram: 'revise' (in nodes/prioritisation) and 'drop_failing'
  (in nodes/validation).
- The linear analysis spine: START -> intake -> coverage -> redundancy
  -> retrieval -> scoring.
- Conditional edge for the COVERAGE-FLOOR GATE (revise loop vs proceed).
- Conditional edge for the VALIDATION LOOP routing (retry / drop-and-flag / pass)
  using gen_retry_count and MAX_GEN_RETRIES.
- interrupt() placement for the 3 HITL checkpoints.
- compile(checkpointer=...) so the graph can pause/resume.
This file is the architecture made executable — it mirrors the Mermaid diagram.
"""
