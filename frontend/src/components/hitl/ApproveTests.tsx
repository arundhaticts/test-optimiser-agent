import { useState } from "react";
import { Loader2, CheckCircle2, XCircle, Target, Terminal } from "lucide-react";
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
    const ids = payload.generated_tests.filter((g) => checked[g.id]).map((g) => g.id);
    onApprove(ids);
  }

  return (
    <div className="hitl-card">
      <div className="hitl-head">
        <span className="hitl-step" style={{ color: "var(--violet)" }}>
          Gate 3 of 3 · Human-in-the-loop
        </span>
        <h2>Code sandbox inspector</h2>
        <p className="muted">
          Each drafted test is shown beside the requirement gap it addresses. Only tests that passed the
          sandbox syntax/import check can be accepted.
        </p>
      </div>

      {payload.generated_tests.length === 0 ? (
        <p className="muted">No tests were generated.</p>
      ) : (
        payload.generated_tests.map((g) => {
          const valid = g.valid !== false;
          return (
            <div key={g.id} className="gen-test">
              <label className="gen-head">
                <input type="checkbox" checked={!!checked[g.id]} disabled={busy} onChange={() => toggle(g.id)} />
                <span className="mono gen-name">{g.id}</span>
                {valid ? (
                  <span className="badge badge-valid">
                    <CheckCircle2 size={12} /> sandbox passed
                  </span>
                ) : (
                  <span className="badge badge-invalid">
                    <XCircle size={12} /> failed check
                  </span>
                )}
              </label>

              {/* Split-screen: drafted code ↔ the uncovered requirement */}
              <div className="mt-3 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--muted)]">
                    <Terminal size={12} /> Drafted test
                  </div>
                  <pre className="code !mt-0">{g.code}</pre>
                </div>
                <div>
                  <div className="mb-1 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--muted)]">
                    <Target size={12} /> Addresses gap
                  </div>
                  <div className="rounded-[8px] border border-[var(--border-strong)] bg-[var(--surface)] p-3.5">
                    <span className="badge badge-reason">{g.criterion_id}</span>
                    <p className="mt-2 text-sm text-[var(--text-2)]">{g.addresses}</p>
                  </div>
                </div>
              </div>
            </div>
          );
        })
      )}

      {payload.dropped.length > 0 && (
        <div className="dropped">
          <h3 className="flex items-center gap-2">
            <XCircle size={16} className="text-[var(--red)]" /> Dropped after 3 retries — needs manual attention
          </h3>
          {payload.dropped.map((d) => (
            <div key={d.id} className="mt-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mono font-semibold">{d.id}</span>
                {d.criterion_id && <span className="badge badge-reason">{d.criterion_id}</span>}
              </div>
              <pre className="code !mt-2 border-[var(--red-d)] !text-[#ff9d96]">
                {d.reason ?? "Generated test exhausted its validation retries (syntax/import check failed)."}
              </pre>
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
