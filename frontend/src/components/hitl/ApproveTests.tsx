import { useState } from "react";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import type { TestsPayload } from "../../types";

export default function ApproveTests({
  payload,
  onApprove,
  busy,
}: {
  payload: TestsPayload;
  onApprove: (approvedIds: string[]) => void;
  busy: boolean;
}) {
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    for (const g of payload.generated_tests) init[g.id] = payload.recommended.includes(g.id);
    return init;
  });

  function toggle(id: string) {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function approve() {
    // Only generated (valid) tests can be approved — dropped tests are never included.
    const ids = payload.generated_tests.filter((g) => checked[g.id]).map((g) => g.id);
    onApprove(ids);
  }

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step">Checkpoint 3 of 3</span>
        <h2>Approve generated tests</h2>
        <p className="muted">Select which drafted tests to include in the optimised plan.</p>
      </div>

      {payload.generated_tests.length === 0 ? (
        <p className="muted">No tests were generated.</p>
      ) : (
        payload.generated_tests.map((g) => (
          <div key={g.id} className="gen-test">
            <label className="gen-head">
              <input
                type="checkbox"
                checked={!!checked[g.id]}
                disabled={busy}
                onChange={() => toggle(g.id)}
              />
              <span className="mono gen-name">{g.id}</span>
              <span className="badge badge-reason">covers {g.criterion_id}</span>
              {g.valid === false ? (
                <span className="badge badge-invalid">
                  <XCircle size={12} /> invalid
                </span>
              ) : (
                <span className="badge badge-valid">
                  <CheckCircle2 size={12} /> valid
                </span>
              )}
            </label>
            <p className="gen-addr">{g.addresses}</p>
            <pre className="code">{g.code}</pre>
          </div>
        ))
      )}

      {payload.dropped.length > 0 && (
        <div className="dropped">
          <h3>Could not generate</h3>
          {payload.dropped.map((d) => (
            <div key={d.id} className="dropped-row">
              <span className="mono">{d.id}</span>
              {d.criterion_id && <span className="badge badge-reason">{d.criterion_id}</span>}
              <span className="muted">{d.reason ?? "dropped after validation retries"}</span>
            </div>
          ))}
        </div>
      )}

      <button className="btn btn-primary" onClick={approve} disabled={busy}>
        {busy && <Loader2 className="spin" size={16} />} Approve Tests
      </button>
    </div>
  );
}
