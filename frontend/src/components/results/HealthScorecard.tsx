import type { Scorecard } from "../../types";

function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function scoreClass(score: number | null): string {
  if (score === null || score === undefined) return "score-na";
  if (score <= 3) return "score-red";
  if (score <= 6) return "score-amber";
  return "score-green";
}

/** Hand-rolled SVG radar — no charting dependency. Scores 0–10 map to radius.
 *  null (insufficient evidence) is plotted at centre and its axis label is greyed. */
function Radar({ scorecard }: { scorecard: Scorecard }) {
  const dims = Object.entries(scorecard);
  const n = dims.length;
  if (n < 3) return null; // radar needs ≥3 axes

  const size = 320;
  const c = size / 2;
  const R = c - 54;
  const rings = [2, 4, 6, 8, 10];

  const pointAt = (i: number, value: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = (Math.max(0, Math.min(10, value)) / 10) * R;
    return [c + r * Math.cos(angle), c + r * Math.sin(angle)] as const;
  };

  const poly = dims
    .map(([, e], i) => pointAt(i, e.score ?? 0))
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");

  return (
    <div className="panel flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Health radar">
        {/* grid rings */}
        {rings.map((rv) => (
          <polygon
            key={rv}
            points={dims
              .map((_, i) => pointAt(i, rv))
              .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
              .join(" ")}
            fill="none"
            stroke="var(--border)"
            strokeWidth={1}
          />
        ))}
        {/* axes + labels */}
        {dims.map(([dim, e], i) => {
          const [ax, ay] = pointAt(i, 10);
          const [lx, ly] = pointAt(i, 11.6);
          const na = e.score === null || e.score === undefined;
          return (
            <g key={dim}>
              <line x1={c} y1={c} x2={ax} y2={ay} stroke="var(--border)" strokeWidth={1} />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={11}
                fontWeight={600}
                fill={na ? "var(--muted)" : "var(--text-2)"}
              >
                {titleCase(dim)}
                {na ? " (n/a)" : ` ${e.score}`}
              </text>
            </g>
          );
        })}
        {/* value polygon */}
        <polygon points={poly} fill="rgba(91,140,255,0.22)" stroke="var(--primary)" strokeWidth={2} />
        {dims.map(([dim, e], i) => {
          const [x, y] = pointAt(i, e.score ?? 0);
          const na = e.score === null || e.score === undefined;
          return (
            <circle
              key={dim}
              cx={x}
              cy={y}
              r={na ? 3 : 4}
              fill={na ? "var(--surface)" : "var(--primary)"}
              stroke={na ? "var(--muted)" : "var(--primary)"}
              strokeWidth={1.5}
            />
          );
        })}
      </svg>
      <p className="mt-1 text-[0.72rem] text-[var(--muted)]">
        Scores 0–10 across six dimensions · <span className="text-[var(--muted)]">n/a</span> = insufficient evidence
      </p>
    </div>
  );
}

export default function HealthScorecard({ scorecard }: { scorecard: Scorecard }) {
  const entries = Object.entries(scorecard);
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
      <Radar scorecard={scorecard} />
      <div className="grid-2x3 !grid-cols-1 sm:!grid-cols-2">
        {entries.map(([dim, entry]) => (
          <div key={dim} className={`score-card ${scoreClass(entry.score)}`}>
            <div className="score-card-head">
              <h4>{titleCase(dim)}</h4>
              {entry.score === null || entry.score === undefined ? (
                <span className="score-badge score-na">Needs data</span>
              ) : (
                <span className={`score-num ${scoreClass(entry.score)}`}>{entry.score}</span>
              )}
            </div>
            <p className="score-reason">{entry.reason}</p>
            <span className="score-action">{entry.action}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
