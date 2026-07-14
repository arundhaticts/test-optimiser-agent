// Sticky left sidebar — the triple-view navigation mapping to the system's
// execution phases: Pipeline Control Center, HITL Approval Hub, Analytics.

import { GitBranch, ShieldQuestion, BarChart3, Hourglass, Plus, Activity } from "lucide-react";
import type { Checkpoint } from "../../types";

export type NavView = "pipeline" | "hitl" | "analytics";

const GATE_LABEL: Record<Checkpoint, string> = {
  approve_removals: "Gate 1 · Removals",
  approve_ranking: "Gate 2 · Tiering",
  approve_tests: "Gate 3 · Tests",
};

interface Props {
  nav: NavView;
  onNav: (v: NavView) => void;
  threadId: string | null;
  checkpoint: Checkpoint | null;
  hasResults: boolean;
  progress: { done: number; total: number };
  degraded: boolean;
  onNewRun: () => void;
}

export default function Sidebar({
  nav,
  onNav,
  threadId,
  checkpoint,
  hasResults,
  progress,
  degraded,
  onNewRun,
}: Props) {
  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;

  const items: {
    id: NavView;
    label: string;
    icon: typeof GitBranch;
    enabled: boolean;
    badge?: string;
    badgeTone?: "violet" | "green";
  }[] = [
    { id: "pipeline", label: "Pipeline Control", icon: GitBranch, enabled: !!threadId },
    {
      id: "hitl",
      label: "Review Gates",
      icon: ShieldQuestion,
      enabled: !!checkpoint,
      badge: checkpoint ? "Needs review" : undefined,
      badgeTone: "violet",
    },
    {
      id: "analytics",
      label: "Analytics",
      icon: BarChart3,
      enabled: hasResults,
      badge: hasResults ? "Ready" : undefined,
      badgeTone: "green",
    },
  ];

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
      {/* brand */}
      <div className="flex items-center gap-2.5 border-b border-[var(--border)] px-5 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand,#2f6df6)] text-white">
          <Activity size={18} />
        </span>
        <div className="leading-tight">
          <div className="text-sm font-bold text-[var(--text)]">Test Optimiser</div>
          <div className="text-[0.66rem] uppercase tracking-wider text-[var(--muted)]">
            L3 Agent · Digital Engineering
          </div>
        </div>
      </div>

      {/* nav */}
      <nav className="flex flex-col gap-1 p-3">
        {items.map((it) => {
          const Icon = it.icon;
          const active = nav === it.id;
          return (
            <button
              key={it.id}
              disabled={!it.enabled}
              onClick={() => it.enabled && onNav(it.id)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                active
                  ? "bg-[var(--surface-3)] text-[var(--text)]"
                  : "text-[var(--text-2)] hover:bg-[var(--surface-2)]"
              }`}
            >
              <Icon size={17} className={active ? "text-[var(--primary)]" : ""} />
              <span className="flex-1">{it.label}</span>
              {it.badge && (
                <span
                  className={`rounded-full px-2 py-0.5 text-[0.6rem] font-bold ${
                    it.badgeTone === "violet"
                      ? "bg-[var(--violet-d)]/50 text-[var(--violet)]"
                      : "bg-[var(--green-d)]/50 text-[var(--green)]"
                  }`}
                >
                  {it.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* run context / progress */}
      {threadId && (
        <div className="mx-3 mt-1 rounded-[10px] border border-[var(--border)] bg-[var(--surface-2)] p-3">
          <div className="flex items-center justify-between text-[0.68rem] uppercase tracking-wider text-[var(--muted)]">
            <span>Active run</span>
            {degraded && (
              <span className="font-bold text-[var(--amber)]">degraded</span>
            )}
          </div>
          <div className="mt-1 break-all font-mono text-xs text-[var(--text-2)]">{threadId}</div>

          {checkpoint ? (
            <div className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-[var(--violet)]">
              <Hourglass size={13} /> Paused · {GATE_LABEL[checkpoint]}
            </div>
          ) : (
            <>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--surface-3)]">
                <div
                  className="h-full rounded-full bg-[var(--primary)] transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="mt-1 text-[0.68rem] text-[var(--muted)]">
                {progress.done}/{progress.total} nodes · {pct}%
              </div>
            </>
          )}
        </div>
      )}

      <div className="mt-auto p-3">
        <button className="btn btn-ghost w-full" onClick={onNewRun}>
          <Plus size={16} /> New run
        </button>
      </div>
    </aside>
  );
}
