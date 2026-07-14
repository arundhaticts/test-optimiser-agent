import { useMemo, useState } from "react";
import { Loader2, GripVertical, RotateCcw } from "lucide-react";
import type { RankingPayload, Tiers } from "../../types";

const TIER_ORDER: (keyof Tiers)[] = ["smoke", "regression", "full"];
const TIER_HINT: Record<keyof Tiers, string> = {
  smoke: "every commit",
  regression: "every merge",
  full: "nightly / release",
};

export default function ApproveRanking({
  payload,
  onApprove,
  busy,
}: {
  payload: RankingPayload;
  onApprove: (tiers: Tiers) => void;
  busy: boolean;
}) {
  const initial = payload.prioritised_plan.tiers;
  const [tiers, setTiers] = useState<Tiers>(() => ({
    smoke: [...initial.smoke],
    regression: [...initial.regression],
    full: [...initial.full],
  }));
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<keyof Tiers | null>(null);
  const pctCov = Math.round(payload.projected_coverage * 100);

  const dirty = useMemo(
    () => TIER_ORDER.some((t) => JSON.stringify(tiers[t]) !== JSON.stringify(initial[t])),
    [tiers, initial],
  );

  function moveTo(test: string, dest: keyof Tiers) {
    setTiers((prev) => {
      const next: Tiers = { smoke: [], regression: [], full: [] };
      for (const t of TIER_ORDER) next[t] = prev[t].filter((x) => x !== test);
      if (!next[dest].includes(test)) next[dest].push(test);
      return next;
    });
  }

  function reset() {
    setTiers({ smoke: [...initial.smoke], regression: [...initial.regression], full: [...initial.full] });
  }

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step" style={{ color: "var(--violet)" }}>
          Gate 2 of 3 · Human-in-the-loop
        </span>
        <h2>Verify tiering</h2>
        <p className="muted">Drag tests between Smoke / Regression / Full before generation.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="proj-cov">
          Projected coverage: <strong>{pctCov}%</strong>
        </div>
        {dirty && (
          <button className="btn btn-ghost" onClick={reset} disabled={busy}>
            <RotateCcw size={14} /> Reset to agent proposal
          </button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {TIER_ORDER.map((tier) => {
          const isOver = over === tier;
          return (
            <div
              key={tier}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(tier);
              }}
              onDragLeave={() => setOver((o) => (o === tier ? null : o))}
              onDrop={() => {
                if (dragging) moveTo(dragging, tier);
                setDragging(null);
                setOver(null);
              }}
              className={`rounded-[10px] border bg-[var(--surface-2)] p-3.5 transition-colors ${
                isOver ? "border-[var(--primary)] bg-[var(--surface-3)]" : "border-[var(--border)]"
              }`}
              style={{
                borderTop: `3px solid ${
                  tier === "smoke" ? "var(--green)" : tier === "regression" ? "var(--amber)" : "var(--primary)"
                }`,
              }}
            >
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="!m-0 capitalize">{tier}</h3>
                  <span className="text-[0.7rem] text-[var(--muted)]">{TIER_HINT[tier]}</span>
                </div>
                <span className="rounded-full bg-[var(--surface-3)] px-2.5 py-0.5 text-sm font-semibold text-[var(--muted)]">
                  {tiers[tier].length}
                </span>
              </div>

              {tiers[tier].length === 0 ? (
                <p className="empty-state">Drop tests here</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {tiers[tier].map((t) => (
                    <div
                      key={t}
                      draggable={!busy}
                      onDragStart={() => setDragging(t)}
                      onDragEnd={() => {
                        setDragging(null);
                        setOver(null);
                      }}
                      className={`flex cursor-grab items-center gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-2.5 py-2 font-mono text-[0.8rem] active:cursor-grabbing ${
                        dragging === t ? "opacity-40" : ""
                      }`}
                    >
                      <GripVertical size={14} className="shrink-0 text-[var(--muted)]" />
                      <span className="break-all">{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <button className="btn btn-primary" onClick={() => onApprove(tiers)} disabled={busy}>
        {busy && <Loader2 className="spin" size={16} />} Approve Ranking
      </button>
    </div>
  );
}
