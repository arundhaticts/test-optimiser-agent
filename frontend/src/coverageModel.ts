// Client-side mirror of the prototype coverage model in src/config.py.
// Used ONLY for the Gate-1 live preview so a reviewer can see the removal impact
// before the backend runs. The backend coverage-floor gate remains authoritative —
// this is an estimate, deliberately labelled as such in the UI.
//
// Model (src/config.py): projected = COVERAGE_BASE + COVERAGE_PER_UNIT * units_kept,
// capped at COVERAGE_CAP. Near-duplicate MERGES share a unit (cost 0); quarantining a
// unique (flaky) test drops one unit (cost COVERAGE_PER_UNIT).

export const COVERAGE_CAP = 0.98;
export const COVERAGE_PER_UNIT = 0.06;

/** Estimate projected coverage after removing `unitCostingRemovals` unique tests. */
export function estimateProjected(unitCostingRemovals: number): number {
  return Math.max(0, Math.min(COVERAGE_CAP, COVERAGE_CAP - COVERAGE_PER_UNIT * unitCostingRemovals));
}

export const pct = (v: number) => `${Math.round(v * 100)}%`;
