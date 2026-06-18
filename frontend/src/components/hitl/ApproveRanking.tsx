import { Loader2 } from "lucide-react";
import type { RankingPayload, Tiers } from "../../types";

const TIER_ORDER: (keyof Tiers)[] = ["smoke", "regression", "full"];

export default function ApproveRanking({
  payload,
  onApprove,
  busy,
}: {
  payload: RankingPayload;
  onApprove: (tiers: Tiers) => void;
  busy: boolean;
}) {
  const tiers = payload.prioritised_plan.tiers;
  const pct = Math.round(payload.projected_coverage * 100);

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step">Checkpoint 2 of 3</span>
        <h2>Approve ranking</h2>
        <p className="muted">Confirm the smoke / regression / full tiering before tests are generated.</p>
      </div>

      <div className="proj-cov">
        Projected coverage: <strong>{pct}%</strong>
      </div>

      <div className="tier-cols">
        {TIER_ORDER.map((tier) => (
          <div key={tier} className={`tier-col tier-${tier}`}>
            <h3>
              {tier} <span className="count">{tiers[tier].length}</span>
            </h3>
            {tiers[tier].length === 0 ? (
              <p className="empty-state">No tests in this tier</p>
            ) : (
              tiers[tier].map((t) => (
                <div key={t} className={`chip mono tier-${tier}`}>
                  {t}
                </div>
              ))
            )}
          </div>
        ))}
      </div>

      <button className="btn btn-primary" onClick={() => onApprove(tiers)} disabled={busy}>
        {busy && <Loader2 className="spin" size={16} />} Approve Ranking
      </button>
    </div>
  );
}
