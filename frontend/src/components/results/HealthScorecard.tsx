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

export default function HealthScorecard({ scorecard }: { scorecard: Scorecard }) {
  const entries = Object.entries(scorecard);
  return (
    <div className="grid-2x3">
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
  );
}
