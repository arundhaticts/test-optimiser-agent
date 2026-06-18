import { useState } from "react";
import { Lock, Loader2 } from "lucide-react";
import type { RemovalsPayload } from "../../types";

export default function ApproveRemovals({
  payload,
  onApprove,
  busy,
}: {
  payload: RemovalsPayload;
  onApprove: (approvedIds: string[]) => void;
  busy: boolean;
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

  function approve() {
    const ids = payload.candidates.filter((c) => !c.pinned && checked[c.test_id]).map((c) => c.test_id);
    onApprove(ids);
  }

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step">Checkpoint 1 of 3</span>
        <h2>Approve removals</h2>
        <p className="muted">Quarantine is reversible; pinned (risk-area) tests are never removed.</p>
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
                    <span className="pin-label">
                      <Lock size={12} /> protected
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
