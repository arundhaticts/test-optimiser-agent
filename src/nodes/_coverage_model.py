"""
Shared coverage model — used by Node 2 (coverage) and the coverage-floor gate so both
compute coverage the same way (Blocker #2's `recompute_coverage`).

Each test belongs to a coverage "unit"; near-duplicate tests (grouped in
redundancy_flags) share a unit. Projected coverage counts distinct units that still
have at least one kept test, so removing a redundant duplicate costs nothing while
removing a unique test drops coverage — the behaviour the floor gate protects.

Shared helper module — not a graph node (no state in/out). One place so coverage,
prioritisation, the coverage-floor gate, and revise all compute coverage identically.

Architecture position: shared helper for the pipeline (used across Node 2 coverage,
Node 6 prioritisation, the coverage_floor_gate router, and revise_node).

Called by: src/nodes/coverage.py, src/nodes/prioritisation.py (prioritisation_node,
coverage_floor_gate, revise_node).
Data in: operates on plain arguments only (not TestOptimiserState).
Data out: returns a float; writes no state.
"""

from src.config import COVERAGE_BASE, COVERAGE_PER_UNIT, COVERAGE_CAP


def _unit_of(test_id: str, clusters: list[list[str]]) -> str:
    """Map a test id to its coverage "unit".

    Purpose: near-duplicate tests share one coverage unit so a duplicate can be dropped
        without losing coverage; a unique test is its own unit.
    Inputs: test_id (str); clusters (list of near-duplicate id groups from
        redundancy_flags).
    Outputs: the unit key — "cluster:<i>" if the test is in a near-duplicate cluster,
        else "test:<id>".
    Side effects: None (pure).
    Called by: coverage_for.
    Calls: (none).
    """
    # WHY: a test in a near-duplicate cluster collapses to that cluster's shared unit,
    # so removing one member of the cluster does not remove the unit.
    for i, cluster in enumerate(clusters):
        if test_id in cluster:
            return f"cluster:{i}"
    # WHY: not clustered -> the test is its own unique coverage unit.
    return f"test:{test_id}"


def coverage_for(tests: list[dict], removals: list[str],
                 redundancy_flags: list[dict] | None = None) -> float:
    """Projected coverage if `removals` were applied.

    Purpose: the single coverage formula used everywhere — distinct covered units scaled
        into a coverage fraction, so removing a duplicate costs nothing but removing a
        unique test lowers coverage.
    Inputs: tests (normalised suite); removals (list of test ids to drop);
        redundancy_flags (near-duplicate clusters; only the "cluster" lists are used).
    Outputs: projected coverage as a float, clamped to COVERAGE_CAP, rounded to 3 dp.
    Side effects: None (pure).
    Called by: coverage_node, prioritisation_node, coverage_floor_gate, revise_node.
    Calls: _unit_of.
    """
    # WHY: only the cluster id-lists matter for unit grouping; ignore flags with no cluster.
    clusters = [f["cluster"] for f in (redundancy_flags or []) if f.get("cluster")]
    removed = set(removals or [])
    # WHY: count DISTINCT units still covered by at least one kept test. Set comprehension
    # dedupes cluster members to a single unit, so dropping a duplicate keeps its unit.
    covered_units = {
        _unit_of(t["id"], clusters) for t in tests if t["id"] not in removed
    }
    # WHY: coverage unit math — a fixed base plus a per-unit increment, capped so the
    # result stays a sensible fraction (see COVERAGE_BASE/PER_UNIT/CAP in config).
    coverage = COVERAGE_BASE + COVERAGE_PER_UNIT * len(covered_units)
    return round(min(coverage, COVERAGE_CAP), 3)
