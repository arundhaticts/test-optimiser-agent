import { AlertCircle, CheckCircle2, CircleSlash } from "lucide-react";
import type { CoverageGapMap } from "../../types";

export default function CoverageMap({ data }: { data: CoverageGapMap }) {
  const rows = Object.entries(data.coverage_map);
  const pct = Math.round(data.projected_coverage * 100);

  return (
    <div className="section">
      <div className="proj-cov">
        Projected coverage after plan: <strong>{pct}%</strong>
      </div>

      <h3>Coverage map</h3>
      <table className="rows">
        <thead>
          <tr>
            <th>Criterion</th>
            <th>Tests covering it</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([cid, tests]) => (
            <tr key={cid}>
              <td className="mono">{cid}</td>
              <td>
                {tests.length ? (
                  tests.map((t) => (
                    <span key={t} className="chip mono">
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="empty-state">no test covers this criterion</span>
                )}
              </td>
              <td>
                {tests.length ? (
                  <span className="status-covered">
                    <CheckCircle2 size={15} /> covered
                  </span>
                ) : (
                  <span className="status-gap">
                    <CircleSlash size={15} /> gap
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Gaps</h3>
      {data.gaps.length === 0 ? (
        <p className="muted">No coverage gaps.</p>
      ) : (
        data.gaps.map((g) => (
          <div key={g.criterion_id} className="gap-card">
            <div className="gap-head">
              <span className="mono">{g.criterion_id}</span>
              {g.risk && (
                <span className="badge badge-invalid">
                  <AlertCircle size={12} /> risk
                </span>
              )}
            </div>
            <p>{g.text}</p>
            <span className="muted">best match: {g.max_similarity.toFixed(2)}</span>
          </div>
        ))
      )}
    </div>
  );
}
