"""Node functions for the Test Optimiser graph.

Package of the 10 work nodes (one file each) plus the auxiliary routers/nodes:
`revise_node` and `coverage_floor_gate` live in `prioritisation.py`;
`route_after_validation` and `drop_failing_node` live in `validation.py`; the shared
coverage math lives in `_coverage_model.py`. Each node is a plain function
`node(state: TestOptimiserState) -> dict` returning only the state keys it changed;
routers return the name (str) of the next node. All nodes are registered and wired in
`src/graph.py`.

Architecture position: the whole analysis/optimisation pipeline. Spine is
intake -> coverage -> redundancy -> retrieval -> scoring, then HITL 1, the
prioritisation/coverage-floor loop, HITL 2, the gap-generation/validation loop, HITL 3,
and finally assemble -> report -> END.

Called by: src/graph.py (imports and registers every node function here).
"""
