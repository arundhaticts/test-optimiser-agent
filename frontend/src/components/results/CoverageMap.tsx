import { AlertCircle, CheckCircle2, CircleSlash, FileCheck2 } from "lucide-react";
import type { CoverageGapMap } from "../../types";

export default function CoverageMap({ data }: { data: CoverageGapMap }) {
  const rows = Object.entries(data.coverage_map);
  const pct = Math.round(data.projected_coverage * 100);
  // criterion_id -> gap (so the table can show "drafted" for an addressed gap)
  const gapById = Object.fromEntries(data.gaps.map((g) => [g.criterion_id, g]));

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
          {rows.map(([cid, tests]) => {
            const addressedBy = gapById[cid]?.addressed_by;
            return (
              <tr key={cid}>
                <td className="mono">{cid}</td>
                <td>
                  {tests.length ? (
                    tests.map((t) => (
                      <span key={t} className="chip mono">
                        {t}
                      </span>
                    ))
                  ) : addressedBy ? (
                    <span className="chip mono chip-new">{addressedBy}</span>
                  ) : (
                    <span className="empty-state">no test covers this criterion</span>
                  )}
                </td>
                <td>
                  {tests.length ? (
                    <span className="status-covered">
                      <CheckCircle2 size={15} /> covered
                    </span>
                  ) : addressedBy ? (
                    <span className="status-drafted">
                      <FileCheck2 size={15} /> gap · test drafted
                    </span>
                  ) : (
                    <span className="status-gap">
                      <CircleSlash size={15} /> gap
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
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
            {g.addressed_by && (
              <div className="addressed">
                <FileCheck2 size={14} /> Addressed by a generated test:{" "}
                <span className="mono">{g.addressed_by}</span>{" "}
                <span className="muted">(drafted — implement &amp; merge to close the gap)</span>
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
