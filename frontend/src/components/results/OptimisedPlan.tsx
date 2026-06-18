import type { OptimisedPlan as Plan, Tiers } from "../../types";

const TIER_ORDER: (keyof Tiers)[] = ["smoke", "regression", "full"];

export default function OptimisedPlan({ plan }: { plan: Plan }) {
  const pct = Math.round(plan.projected_coverage * 100);
  const optimisedCount = plan.proposed.kept.length + plan.proposed.generated.length;

  return (
    <div className="section">
      <div className="summary-line">
        {plan.current.total_tests} → {optimisedCount} tests · Coverage: <strong>{pct}%</strong> · Goal:{" "}
        <span className="badge badge-reason">{plan.goal}</span>
      </div>

      <div className="plan-cols">
        <div className="plan-col">
          <h3>Current ({plan.current.total_tests})</h3>
          {plan.current.test_ids.map((t) => (
            <div key={t} className="chip mono">
              {t}
            </div>
          ))}
        </div>

        <div className="plan-col">
          <h3>Proposed</h3>

          <div className="plan-block">
            <h4>Tiers</h4>
            {TIER_ORDER.map((tier) => (
              <div key={tier} className="tier-line">
                <span className={`tier-tag tier-${tier}`}>{tier}</span>
                <span>
                  {plan.proposed.tiers[tier].length ? (
                    plan.proposed.tiers[tier].map((t) => (
                      <span key={t} className={`chip mono tier-${tier}`}>
                        {t}
                      </span>
                    ))
                  ) : (
                    <span className="empty-state">empty</span>
                  )}
                </span>
              </div>
            ))}
          </div>

          <div className="plan-block">
            <h4>Removals</h4>
            {plan.proposed.removed.length ? (
              plan.proposed.removed.map((t) => (
                <div key={t} className="chip mono chip-strike">
                  {t} <span className="badge-removed">removed</span>
                </div>
              ))
            ) : (
              <p className="empty-state">No removals.</p>
            )}
          </div>

          <div className="plan-block">
            <h4>Generated</h4>
            {plan.proposed.generated.length ? (
              plan.proposed.generated.map((t) => (
                <div key={t} className="chip mono chip-new">
                  {t}
                </div>
              ))
            ) : (
              <p className="empty-state">None approved.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
