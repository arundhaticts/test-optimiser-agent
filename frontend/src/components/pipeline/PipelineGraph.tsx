// View A — Pipeline Control Center. A dynamic vertical tree of the LangGraph
// spine with per-node status markers (Idle / Running / Completed / Degraded /
// Awaiting-human). Purely presentational; status is computed in pipeline.ts.

import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  ShieldQuestion,
} from "lucide-react";
import type { NodeStatus, StepState } from "../../pipeline";

const STATUS_META: Record<
  NodeStatus,
  { label: string; dot: string; text: string; ring: string }
> = {
  idle: { label: "Idle", dot: "bg-[var(--surface-3)]", text: "text-[var(--muted)]", ring: "border-[var(--border)]" },
  running: { label: "Running", dot: "bg-[var(--primary)]", text: "text-[var(--primary)]", ring: "border-[var(--primary)]" },
  completed: { label: "Completed", dot: "bg-[var(--green)]", text: "text-[var(--green)]", ring: "border-[var(--green-d)]" },
  degraded: { label: "Degraded", dot: "bg-[var(--amber)]", text: "text-[var(--amber)]", ring: "border-[var(--amber-d)]" },
  awaiting: { label: "Awaiting human", dot: "bg-[var(--violet)]", text: "text-[var(--violet)]", ring: "border-[var(--violet)]" },
};

function StatusIcon({ status }: { status: NodeStatus }) {
  const cls = STATUS_META[status].text;
  switch (status) {
    case "completed":
      return <CheckCircle2 className={cls} size={20} />;
    case "running":
      return <Loader2 className={`${cls} spin`} size={20} />;
    case "degraded":
      return <AlertTriangle className={cls} size={20} />;
    case "awaiting":
      return <ShieldQuestion className={cls} size={20} />;
    default:
      return <Circle className={cls} size={20} />;
  }
}

export default function PipelineGraph({ steps }: { steps: StepState[] }) {
  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-5">
        <h2 className="!m-0">Pipeline Control Center</h2>
        <span className="text-xs text-[var(--muted)] font-mono">LangGraph orchestration spine</span>
      </div>

      <ol className="relative flex flex-col">
        {steps.map((step, i) => {
          const meta = STATUS_META[step.status];
          const isLast = i === steps.length - 1;
          const active = step.status === "running" || step.status === "awaiting";
          return (
            <li key={step.key} className="relative flex gap-4 pb-2">
              {/* connector rail */}
              <div className="flex flex-col items-center">
                <span
                  className={`relative z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 bg-[var(--surface)] ${meta.ring} ${active ? "shadow-[0_0_0_4px_rgba(91,140,255,0.12)]" : ""}`}
                >
                  <StatusIcon status={step.status} />
                </span>
                {!isLast && (
                  <span
                    className="w-0.5 flex-1 min-h-6"
                    style={{
                      background:
                        step.status === "completed" || step.status === "degraded"
                          ? "var(--green-d)"
                          : "var(--border)",
                    }}
                  />
                )}
              </div>

              {/* node card */}
              <div
                className={`mb-3 flex-1 rounded-[10px] border px-4 py-3 transition-colors ${
                  active
                    ? "border-[var(--border-strong)] bg-[var(--surface-2)]"
                    : "border-[var(--border)] bg-[var(--surface)]"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {step.kind === "gate" && (
                      <span className="rounded-full bg-[var(--violet-d)]/40 px-2 py-0.5 text-[0.62rem] font-bold uppercase tracking-wider text-[var(--violet)]">
                        HITL
                      </span>
                    )}
                    <span className="truncate font-semibold text-[var(--text)]">{step.label}</span>
                  </div>
                  <span className={`whitespace-nowrap text-xs font-semibold ${meta.text}`}>
                    {meta.label}
                  </span>
                </div>
                <div className="mt-1 font-mono text-[0.7rem] text-[var(--muted)]">{step.key}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
