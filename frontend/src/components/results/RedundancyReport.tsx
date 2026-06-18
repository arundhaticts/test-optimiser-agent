import type { RedundancyFlakinessReport } from "../../types";

export default function RedundancyReport({ data }: { data: RedundancyFlakinessReport }) {
  return (
    <div className="section">
      <h3>Duplicates</h3>
      {data.redundancy_flags.length === 0 ? (
        <p className="muted">No near-duplicate clusters.</p>
      ) : (
        data.redundancy_flags.map((f, i) => (
          <div key={i} className="flag-card">
            <div>
              <span className="mono bold">{f.keep}</span> <span className="muted">keep</span>
              {f.redundant.map((r) => (
                <span key={r} className="chip mono chip-strike">
                  {r}
                </span>
              ))}
            </div>
            <p className="evidence">{f.evidence}</p>
            <span className="label">{f.action}</span>
          </div>
        ))
      )}

      <h3>Flaky</h3>
      {data.flakiness_flags.length === 0 ? (
        <p className="muted">No flaky tests.</p>
      ) : (
        data.flakiness_flags.map((f) => (
          <div key={f.test_id} className="flag-card">
            <span className="mono">{f.test_id}</span>
            <div className="bar">
              <div className="bar-fill bar-red" style={{ width: `${Math.round(f.fail_rate * 100)}%` }} />
              <span className="bar-label">{Math.round(f.fail_rate * 100)}% fail</span>
            </div>
            <p className="evidence">{f.evidence}</p>
            <span className="label">{f.action}</span>
          </div>
        ))
      )}

      <h3>Slow</h3>
      {data.slow_flags.length === 0 ? (
        <p className="muted">No slow tests.</p>
      ) : (
        data.slow_flags.map((f) => (
          <div key={f.test_id} className="flag-card">
            <span className="mono">{f.test_id}</span> <strong>{f.avg_seconds}s avg</strong>
            <p className="evidence">{f.evidence}</p>
            <span className="label">{f.action}</span>
          </div>
        ))
      )}
    </div>
  );
}
