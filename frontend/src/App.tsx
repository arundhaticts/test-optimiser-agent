import { useEffect, useState } from "react";
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
import InputPanel from "./components/InputPanel";
import AuditLog from "./components/AuditLog";
import DegradedBanner from "./components/DegradedBanner";
import ApproveRemovals from "./components/hitl/ApproveRemovals";
import ApproveRanking from "./components/hitl/ApproveRanking";
import ApproveTests from "./components/hitl/ApproveTests";
import ResultsTabs from "./components/results/ResultsTabs";

type AppView = "input" | "running" | "hitl" | "results";

export default function App() {
  const [view, setView] = useState<AppView>("input");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);
  const [hitlPayload, setHitlPayload] = useState<HitlPayload | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [toolErrors, setToolErrors] = useState<ToolError[]>([]);
  const [outputs, setOutputs] = useState<Outputs | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  function applyResult(res: RunResult) {
    if (res.status === "completed") {
      setOutputs(res.outputs);
      if (res.outputs.audit_log) setAuditLog(res.outputs.audit_log);
      setToolErrors(res.outputs.tool_errors ?? []);
      setCheckpoint(null);
      setHitlPayload(null);
      setView("results");
    } else {
      setCheckpoint(res.checkpoint);
      setHitlPayload(res.payload);
      setView("hitl");
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
    setBusy(true);
    setView("running");
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
    try {
      applyResult(await resumeRun(threadId, decision));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setView("hitl"); // stay on the card so the user can retry
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setView("input");
    setThreadId(null);
    setCheckpoint(null);
    setHitlPayload(null);
    setAuditLog([]);
    setToolErrors([]);
    setOutputs(null);
    setError(null);
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Test Optimiser Agent</h1>
        {threadId && <span className="thread">run: {threadId}</span>}
      </header>

      <main className="main">
        {view === "input" && <InputPanel onRun={handleRun} busy={busy} error={error} />}

        {(view === "running" || view === "hitl") && (
          <div className="run-layout">
            <div className="run-main">
              <DegradedBanner toolErrors={toolErrors} />
              {error && <div className="banner banner-error">{error}</div>}

              {view === "running" && (
                <div className="panel running-panel">
                  <Loader2 className="spin" size={28} />
                  <p>The agent is working… this can take a little while on the first LLM call.</p>
                </div>
              )}

              {view === "hitl" &&
                hitlPayload?.checkpoint === "approve_removals" &&
                checkpoint === "approve_removals" && (
                  <ApproveRemovals payload={hitlPayload} onApprove={(ids) => handleResume(ids)} busy={busy} />
                )}
              {view === "hitl" &&
                hitlPayload?.checkpoint === "approve_ranking" &&
                checkpoint === "approve_ranking" && (
                  <ApproveRanking
                    payload={hitlPayload}
                    onApprove={(tiers: Tiers) => handleResume(tiers)}
                    busy={busy}
                  />
                )}
              {view === "hitl" &&
                hitlPayload?.checkpoint === "approve_tests" &&
                checkpoint === "approve_tests" && (
                  <ApproveTests payload={hitlPayload} onApprove={(ids) => handleResume(ids)} busy={busy} />
                )}
            </div>

            <aside className="run-side">
              <AuditLog entries={auditLog} />
            </aside>
          </div>
        )}

        {view === "results" && outputs && (
          <div className="results-layout">
            <DegradedBanner toolErrors={toolErrors} />
            <div className="results-head">
              <h2>Results</h2>
              <button className="btn btn-primary" onClick={reset}>
                Run Another
              </button>
            </div>
            <ResultsTabs outputs={outputs} />
          </div>
        )}
      </main>
    </div>
  );
}
