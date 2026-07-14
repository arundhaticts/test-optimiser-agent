import { useMemo, useState } from "react";
import { ShieldCheck, Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";
import type { RemovalsPayload } from "../../types";
import { estimateProjected, pct } from "../../coverageModel";

export default function ApproveRemovals({
  payload,
  onApprove,
  busy,
  coverageTarget,
}: {
  payload: RemovalsPayload;
  onApprove: (approvedIds: string[]) => void;
  busy: boolean;
  coverageTarget: number;
}) {
  // Default: every non-pinned recommended candidate is checked. Pinned tests can never
  // be selected (protected from removal).
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const c of payload.candidates) init[c.test_id] = !c.pinned && payload.recommended.includes(c.test_id);
    return init;
  });

  function toggle(id: string, pinned: boolean) {
    if (pinned) return;
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  // Live optimisation math — a merge (near-duplicate) costs no coverage; quarantining a
  // unique/flaky test costs one unit. Estimate, not the authoritative floor gate.
  const { selectedCount, unitCosting, projected, breach } = useMemo(() => {
    const selected = payload.candidates.filter((c) => !c.pinned && checked[c.test_id]);
    const unit = selected.filter((c) => c.kind !== "merge").length;
    const proj = estimateProjected(unit);
    return {
      selectedCount: selected.length,
      unitCosting: unit,
      projected: proj,
      breach: proj < coverageTarget,
    };
  }, [payload.candidates, checked, coverageTarget]);

  function approve() {
    const ids = payload.candidates.filter((c) => !c.pinned && checked[c.test_id]).map((c) => c.test_id);
    onApprove(ids);
  }

  const headroomPct = Math.max(0, Math.min(100, (projected / Math.max(coverageTarget, 0.01)) * 100));

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step" style={{ color: "var(--violet)" }}>
          Gate 1 of 3 · Human-in-the-loop
        </span>
        <h2>Approve removals</h2>
        <p className="muted">Quarantine is reversible; pinned (risk-area) tests are never removed.</p>
      </div>

      {/* Live optimisation math */}
      <div
        className={`rounded-[10px] border px-4 py-3 ${
          breach ? "border-[var(--red-d)] bg-[#2a1416]" : "border-[var(--border)] bg-[var(--surface-2)]"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-5 text-sm">
            <span className="text-[var(--text-2)]">
              Selected <strong className="text-[var(--text)]">{selectedCount}</strong>
              <span className="text-[var(--muted)]"> ({unitCosting} coverage-costing)</span>
            </span>
            <span className="text-[var(--text-2)]">
              Est. projected coverage{" "}
              <strong className={breach ? "text-[var(--red)]" : "text-[var(--green)]"}>{pct(projected)}</strong>
              <span className="text-[var(--muted)]"> · target {pct(coverageTarget)}</span>
            </span>
          </div>
          {breach ? (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--red)]">
              <AlertTriangle size={14} /> Below floor — backend gate will block this set
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--green)]">
              <CheckCircle2 size={14} /> Above coverage floor
            </span>
          )}
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--surface-3)]">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${headroomPct}%`, background: breach ? "var(--red)" : "var(--green)" }}
          />
        </div>
        <div className="mt-1 text-[0.68rem] text-[var(--muted)]">
          Estimate from the prototype coverage model — the backend coverage-floor gate is authoritative.
        </div>
      </div>

      {payload.candidates.length === 0 ? (
        <p className="muted">No removal candidates — nothing to quarantine or merge.</p>
      ) : (
        <table className="rows">
          <thead>
            <tr>
              <th></th>
              <th>Test</th>
              <th>Reason</th>
              <th>Evidence</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {payload.candidates.map((c) => (
              <tr key={c.test_id} className={c.pinned ? "pinned" : ""}>
                <td>
                  <input
                    type="checkbox"
                    checked={!!checked[c.test_id]}
                    disabled={c.pinned || busy}
                    onChange={() => toggle(c.test_id, c.pinned)}
                  />
                </td>
                <td className="mono col-test">
                  {c.test_id}
                  {c.pinned && (
                    <span
                      className="ml-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.68rem] font-bold"
                      style={{ color: "var(--brand-2,#5b8cff)", borderColor: "var(--primary-d)", background: "#132043" }}
                    >
                      <ShieldCheck size={12} /> Protected by Policy
                    </span>
                  )}
                </td>
                <td>
                  <span className="badge badge-kind">{c.reason}</span>
                </td>
                <td className="evidence">{c.evidence}</td>
                <td>
                  <span className="badge badge-action">{c.kind}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="btn-row">
        <button className="btn btn-primary" onClick={approve} disabled={busy}>
          {busy && <Loader2 className="spin" size={16} />} Approve Selected
        </button>
        <button className="btn btn-ghost" onClick={() => onApprove([])} disabled={busy}>
          Skip — keep all tests
        </button>
      </div>
    </div>
  );
}
