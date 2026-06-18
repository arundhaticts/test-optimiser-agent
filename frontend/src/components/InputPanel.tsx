import { useState } from "react";
import { Play, Loader2, Gauge, Target, Layers } from "lucide-react";
import type { Goal, RunMode, RunRequest } from "../types";

const GOALS: Goal[] = ["speed", "coverage", "reliability", "cost"];

const RUN_MODE_TIPS: Record<RunMode, string> = {
  interactive: "You review and approve each of the 3 checkpoints in the browser.",
  automated: "The agent auto-approves the recommended choices and runs straight through.",
};

export default function InputPanel({
  onRun,
  busy,
  error,
}: {
  onRun: (req: RunRequest) => void;
  busy: boolean;
  error: string | null;
}) {
  const [suitePath, setSuitePath] = useState("sample_data/sample_suite");
  const [projectId, setProjectId] = useState("demo");
  const [goal, setGoal] = useState<Goal>("speed");
  const [coveragePct, setCoveragePct] = useState(80); // shown as %, stored as 0–1
  const [riskAreas, setRiskAreas] = useState("payment");
  const [runMode, setRunMode] = useState<RunMode>("interactive");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onRun({
      suite_path: suitePath.trim(),
      project_id: projectId.trim() || "demo",
      optimization_goal: goal,
      coverage_target: Math.min(100, Math.max(0, coveragePct)) / 100,
      risk_areas: riskAreas
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      run_mode: runMode,
    });
  }

  return (
    <div className="input-wrap">
      <div className="hero">
        <h1 className="hero-title">Make your test suite leaner, faster, more reliable</h1>
        <p className="hero-sub">
          Score suite health, map coverage against acceptance criteria, flag flaky / slow /
          duplicate tests, and get a re-prioritised plan — you approve every change.
        </p>
        <div className="hero-feats">
          <span className="feat">
            <Gauge size={15} /> Health scorecard
          </span>
          <span className="feat">
            <Target size={15} /> Coverage gaps
          </span>
          <span className="feat">
            <Layers size={15} /> Smoke / regression / full
          </span>
        </div>
      </div>

      <form className="panel input-panel" onSubmit={submit}>
        <h2>Run a test-suite analysis</h2>

        <div className="input-grid">
          <label>
            Suite path
            <input value={suitePath} onChange={(e) => setSuitePath(e.target.value)} required />
          </label>

          <label>
            Project ID
            <input value={projectId} onChange={(e) => setProjectId(e.target.value)} required />
          </label>

          <label>
            Optimization goal
            <select value={goal} onChange={(e) => setGoal(e.target.value as Goal)}>
              {GOALS.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>

          <label>
            Coverage target
            <input
              type="number"
              min={0}
              max={100}
              value={coveragePct}
              onChange={(e) => setCoveragePct(Number(e.target.value))}
            />
          </label>

          <label>
            <span>
              Risk areas <span className="hint">(comma-separated)</span>
            </span>
            <input value={riskAreas} onChange={(e) => setRiskAreas(e.target.value)} />
          </label>

          <div className="field">
            <span>Run mode</span>
            <div className="toggle">
              {(["interactive", "automated"] as RunMode[]).map((m) => (
                <button
                  type="button"
                  key={m}
                  className={runMode === m ? "toggle-btn active" : "toggle-btn"}
                  onClick={() => setRunMode(m)}
                  data-tip={RUN_MODE_TIPS[m]}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          {busy ? "Running…" : "Run Analysis"}
        </button>
      </form>
    </div>
  );
}
