import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { getRun, resumeRun, startRun } from "./api";
import type {
  AuditEntry,
  Checkpoint,
  Decision,
  HitlPayload,
  Outputs,
  RunRequest,
  RunResult,
  Tiers,
  ToolError,
} from "./types";
import { computeSteps, progress } from "./pipeline";
import InputPanel from "./components/InputPanel";
import AuditLog from "./components/AuditLog";
import DegradedBanner from "./components/DegradedBanner";
import ApproveRemovals from "./components/hitl/ApproveRemovals";
import ApproveRanking from "./components/hitl/ApproveRanking";
import ApproveTests from "./components/hitl/ApproveTests";
import ResultsTabs from "./components/results/ResultsTabs";
import Sidebar, { type NavView } from "./components/layout/Sidebar";
import PipelineGraph from "./components/pipeline/PipelineGraph";

type AppView = "input" | "running" | "hitl" | "results";

export default function App() {
  const [view, setView] = useState<AppView>("input");
  const [nav, setNav] = useState<NavView>("pipeline");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);
  const [hitlPayload, setHitlPayload] = useState<HitlPayload | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [toolErrors, setToolErrors] = useState<ToolError[]>([]);
  const [outputs, setOutputs] = useState<Outputs | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [coverageTarget, setCoverageTarget] = useState(0.8);

  // While a (blocking) request is in flight, poll the live audit log so the feed
  // animates. 404s before the run registers are ignored by getRun.
  useEffect(() => {
    if (!busy || !threadId) return;
    const id = setInterval(async () => {
      const snap = await getRun(threadId);
      if (snap) {
        setAuditLog(snap.audit_log);
        setToolErrors(snap.tool_errors);
      }
    }, 2000);
    return () => clearInterval(id);
  }, [busy, threadId]);

  const steps = useMemo(
    () =>
      computeSteps(auditLog, toolErrors, {
        busy,
        checkpoint,
        done: view === "results",
      }),
    [auditLog, toolErrors, busy, checkpoint, view],
  );

  function applyResult(res: RunResult) {
    if (res.status === "completed") {
      setOutputs(res.outputs);
      if (res.outputs.audit_log) setAuditLog(res.outputs.audit_log);
      setToolErrors(res.outputs.tool_errors ?? []);
      setCheckpoint(null);
      setHitlPayload(null);
      setView("results");
      setNav("analytics");
    } else {
      setCheckpoint(res.checkpoint);
      setHitlPayload(res.payload);
      setView("hitl");
      setNav("hitl");
      void getRun(res.threadId).then((snap) => {
        if (snap) {
          setAuditLog(snap.audit_log);
          setToolErrors(snap.tool_errors);
        }
      });
    }
  }

  async function handleRun(req: RunRequest) {
    setError(null);
    setOutputs(null);
    setAuditLog([]);
    setToolErrors([]);
    setThreadId(req.project_id);
    setCoverageTarget(req.coverage_target);
    setBusy(true);
    setView("running");
    setNav("pipeline");
    try {
      applyResult(await startRun(req));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setView("input");
    } finally {
      setBusy(false);
    }
  }

  async function handleResume(decision: Decision) {
    if (!threadId) return;
    setError(null);
    setBusy(true);
    setView("running");
    setNav("pipeline");
    try {
      applyResult(await resumeRun(threadId, decision));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setView("hitl"); // stay on the card so the user can retry
      setNav("hitl");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setView("input");
    setNav("pipeline");
    setThreadId(null);
    setCheckpoint(null);
    setHitlPayload(null);
    setAuditLog([]);
    setToolErrors([]);
    setOutputs(null);
    setError(null);
  }

  // Setup screen — full-bleed, no shell yet.
  if (view === "input") {
    return (
      <div className="min-h-screen">
        <header className="topbar">
          <h1>Test Optimiser Agent</h1>
        </header>
        <main className="main">
          <InputPanel onRun={handleRun} busy={busy} error={error} />
        </main>
      </div>
    );
  }

  const degraded = toolErrors.length > 0;
  const navTitle =
    nav === "pipeline" ? "Pipeline Control Center" : nav === "hitl" ? "HITL Approval Hub" : "Analytics & Deliverables";

  return (
    <div className="flex min-h-screen bg-[var(--bg)]">
      <Sidebar
        nav={nav}
        onNav={setNav}
        threadId={threadId}
        checkpoint={checkpoint}
        hasResults={!!outputs}
        progress={progress(steps)}
        degraded={degraded}
        onNewRun={reset}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="topbar !px-8">
          <h1 className="!text-[1.05rem]">{navTitle}</h1>
          {view === "results" && (
            <button className="btn btn-primary ml-auto" onClick={reset}>
              Run Another
            </button>
          )}
        </header>

        <main className="mx-auto w-full max-w-[1320px] flex-1 px-8 py-7">
          <DegradedBanner toolErrors={toolErrors} />
          {error && <div className="banner banner-error">{error}</div>}

          {/* View A — Pipeline Control Center */}
          {nav === "pipeline" && (
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="min-w-0 space-y-4">
                {view === "running" && (
                  <div className="panel running-panel">
                    <Loader2 className="spin" size={26} />
                    <p>The agent is working… this can take a little while on the first LLM call.</p>
                  </div>
                )}
                <PipelineGraph steps={steps} />
              </div>
              <aside className="lg:sticky lg:top-[92px]">
                <AuditLog entries={auditLog} />
              </aside>
            </div>
          )}

          {/* View B — HITL Approval Hub */}
          {nav === "hitl" && (
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
              <div className="min-w-0">
                {view === "running" && (
                  <div className="panel running-panel">
                    <Loader2 className="spin" size={26} />
                    <p>Resuming the run with your decision…</p>
                  </div>
                )}
                {view === "hitl" && hitlPayload?.checkpoint === "approve_removals" && (
                  <ApproveRemovals
                    payload={hitlPayload}
                    onApprove={(ids) => handleResume(ids)}
                    busy={busy}
                    coverageTarget={coverageTarget}
                  />
                )}
                {view === "hitl" && hitlPayload?.checkpoint === "approve_ranking" && (
                  <ApproveRanking payload={hitlPayload} onApprove={(tiers: Tiers) => handleResume(tiers)} busy={busy} />
                )}
                {view === "hitl" && hitlPayload?.checkpoint === "approve_tests" && (
                  <ApproveTests payload={hitlPayload} onApprove={(ids) => handleResume(ids)} busy={busy} />
                )}
                {view !== "hitl" && !checkpoint && (
                  <div className="panel text-[var(--text-2)]">No checkpoint is awaiting review right now.</div>
                )}
              </div>
              <aside className="lg:sticky lg:top-[92px]">
                <AuditLog entries={auditLog} />
              </aside>
            </div>
          )}

          {/* View C — Analytics & Deliverables */}
          {nav === "analytics" &&
            (outputs ? (
              <ResultsTabs outputs={outputs} />
            ) : (
              <div className="panel text-[var(--text-2)]">Results appear here once the run completes.</div>
            ))}
        </main>
      </div>
    </div>
  );
}
