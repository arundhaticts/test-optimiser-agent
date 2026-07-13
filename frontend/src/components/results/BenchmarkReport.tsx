import type { Benchmark, BenchmarkCategory } from "../../types";

// Renders the benchmark comparison of the run's actual findings vs the uploaded (or sample)
// expected-findings answer key. Only shown when outputs.benchmark is present.

const CATEGORY_LABELS: Record<string, string> = {
  duplicates: "Duplicates",
  flaky: "Flaky",
  slow: "Slow",
  coverage_gaps: "Coverage gaps",
};

function pct(v: number | null): string {
  return v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`;
}

// A matched/missing/extra entry is either an id (string) or a cluster (string[]).
function itemLabel(item: string | string[]): string {
  return Array.isArray(item) ? item.join(" + ") : item;
}

function Chips({ items, kind }: { items: (string | string[])[]; kind: string }) {
  if (!items.length) return <span className="muted">—</span>;
  return (
    <div className="chips">
      {items.map((it, i) => (
        <span key={i} className={`chip chip-${kind}`}>
          {itemLabel(it)}
        </span>
      ))}
    </div>
  );
}

export default function BenchmarkReport({ benchmark }: { benchmark: Benchmark }) {
  const { summary, categories } = benchmark;

  return (
    <div className="benchmark">
      {/* Headline score */}
      <div className="benchmark-summary">
        <div className="metric">
          <span className="metric-val">{pct(summary.recall)}</span>
          <span className="metric-label">Recall (found / expected)</span>
        </div>
        <div className="metric">
          <span className="metric-val">{pct(summary.precision)}</span>
          <span className="metric-label">Precision (correct / flagged)</span>
        </div>
        <div className="metric">
          <span className="metric-val">
            {summary.matched_total}/{summary.expected_total}
          </span>
          <span className="metric-label">Matched</span>
        </div>
        <div className="metric">
          <span className="metric-val">{summary.missing_total}</span>
          <span className="metric-label">Missing</span>
        </div>
        <div className="metric">
          <span className="metric-val">{summary.extra_total}</span>
          <span className="metric-label">Extra</span>
        </div>
      </div>

      {/* Per-category breakdown */}
      <table className="rows benchmark-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Recall</th>
            <th>Precision</th>
            <th>Matched</th>
            <th>Missing (expected, not found)</th>
            <th>Extra (found, not expected)</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(categories).map(([key, cat]: [string, BenchmarkCategory]) => (
            <tr key={key}>
              <td className="bold">{CATEGORY_LABELS[key] ?? key}</td>
              <td>{pct(cat.recall)}</td>
              <td>{pct(cat.precision)}</td>
              <td>
                <Chips items={cat.matched} kind="matched" />
              </td>
              <td>
                <Chips items={cat.missing} kind="missing" />
              </td>
              <td>
                <Chips items={cat.extra} kind="extra" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="hint">
        Graded against the {" "}
        {"expected-findings answer key"}. Recall = how many expected findings the agent caught;
        precision = how many of its findings were expected.
      </p>
    </div>
  );
}
