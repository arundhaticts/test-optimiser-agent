"""
Shared coverage model — used by Node 2 (coverage) and the coverage-floor gate so both
compute coverage the same way (Blocker #2's `recompute_coverage`).

Each test belongs to a coverage "unit"; near-duplicate tests (grouped in
redundancy_flags) share a unit. Projected coverage counts distinct units that still
have at least one kept test, so removing a redundant duplicate costs nothing while
removing a unique test drops coverage — the behaviour the floor gate protects.
"""

from src.config import COVERAGE_BASE, COVERAGE_PER_UNIT, COVERAGE_CAP


def _unit_of(test_id: str, clusters: list[list[str]]) -> str:
    for i, cluster in enumerate(clusters):
        if test_id in cluster:
            return f"cluster:{i}"
    return f"test:{test_id}"


def coverage_for(tests: list[dict], removals: list[str],
                 redundancy_flags: list[dict] | None = None) -> float:
    """Projected coverage if `removals` were applied."""
    clusters = [f["cluster"] for f in (redundancy_flags or []) if f.get("cluster")]
    removed = set(removals or [])
    covered_units = {
        _unit_of(t["id"], clusters) for t in tests if t["id"] not in removed
    }
    coverage = COVERAGE_BASE + COVERAGE_PER_UNIT * len(covered_units)
    return round(min(coverage, COVERAGE_CAP), 3)
