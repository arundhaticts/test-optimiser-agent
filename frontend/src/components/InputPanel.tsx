import { useState } from "react";
import { Play, Loader2, Gauge, Target, Layers, Upload, FolderOpen } from "lucide-react";
import type { Goal, RunMode, RunRequest } from "../types";
import { uploadFiles } from "../api";

const GOALS: Goal[] = ["speed", "coverage", "reliability", "cost"];

// Extensions the backend (src/tools/upload_store.py TEST_EXTS) accepts, plus .zip archives.
const ACCEPT = ".py,.js,.jsx,.ts,.tsx,.mjs,.cjs,.java,.go,.rb,.cs,.zip";

const RUN_MODE_TIPS: Record<RunMode, string> = {
  interactive: "You review and approve each of the 3 checkpoints in the browser.",
  automated: "The agent auto-approves the recommended choices and runs straight through.",
};

// Source of the suite under analysis: the bundled sample, or files you upload. Upload runs
// NEVER fall back to the sample_data fixtures — that's what the sample run is for.
type Source = "sample" | "upload";

export default function InputPanel({
  onRun,
  busy,
  error,
}: {
  onRun: (req: RunRequest) => void;
  busy: boolean;
  error: string | null;
}) {
  const [source, setSource] = useState<Source>("sample");
  const [suitePath, setSuitePath] = useState("sample_data/sample_suite");
  const [projectId, setProjectId] = useState("demo");
  const [goal, setGoal] = useState<Goal>("speed");
  const [coveragePct, setCoveragePct] = useState(80); // shown as %, stored as 0–1
  const [riskAreas, setRiskAreas] = useState("payment");
  const [runMode, setRunMode] = useState<RunMode>("interactive");

  // Upload-mode selections
  const [suiteFiles, setSuiteFiles] = useState<File[]>([]);
  const [criteriaFile, setCriteriaFile] = useState<File | null>(null);
  const [ciFile, setCiFile] = useState<File | null>(null);
  const [expectedFile, setExpectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const disabled = busy || uploading;

  function baseRequest(): Omit<
    RunRequest,
    "suite_path" | "criteria_path" | "ci_history_path" | "expected_findings_path"
  > {
    return {
      project_id: projectId.trim() || "demo",
      optimization_goal: goal,
      coverage_target: Math.min(100, Math.max(0, coveragePct)) / 100,
      risk_areas: riskAreas
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      run_mode: runMode,
    };
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setUploadError(null);

    // WHY: sample/demo run — analyse the bundled suite and let criteria/CI default to the
    // sample fixtures (criteria_path / ci_history_path left undefined).
    if (source === "sample") {
      onRun({ ...baseRequest(), suite_path: suitePath.trim() });
      return;
    }

    // WHY: upload run — must have at least one test file; send them to the backend, then run
    // against the returned paths. Any data source NOT uploaded is sent as "" so the backend
    // uses NO source (never the sample fixtures) for a real benchmark.
    if (suiteFiles.length === 0) {
      setUploadError("Select at least one test file (or a .zip) to upload.");
      return;
    }
    setUploading(true);
    try {
      const archives = suiteFiles.filter((f) => f.name.toLowerCase().endsWith(".zip"));
      const files = suiteFiles.filter((f) => !f.name.toLowerCase().endsWith(".zip"));
      const res = await uploadFiles({
        files,
        archives,
        criteria: criteriaFile,
        ciHistory: ciFile,
        expectedFindings: expectedFile,
      });
      if (res.test_count === 0) {
        setUploadError(
          `No tests were recognised in the uploaded files (${res.written.length} file(s) stored). ` +
            `Check they follow a known naming convention (e.g. test_*.py, *.test.ts, *Test.java).`
        );
        return;
      }
      onRun({
        ...baseRequest(),
        suite_path: res.suite_path,
        // "" = "no source, don't use sample data"; a real path = use the uploaded file.
        criteria_path: res.criteria_path ?? "",
        ci_history_path: res.ci_history_path ?? "",
        expected_findings_path: res.expected_findings_path ?? "",
      });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
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

        {/* Source toggle: bundled sample vs uploaded files */}
        <div className="field">
          <span>Test source</span>
          <div className="toggle">
            <button
              type="button"
              className={source === "sample" ? "toggle-btn active" : "toggle-btn"}
              onClick={() => setSource("sample")}
              data-tip="Analyse the bundled sample suite (uses the sample criteria & CI history)."
            >
              <FolderOpen size={15} /> Sample suite
            </button>
            <button
              type="button"
              className={source === "upload" ? "toggle-btn active" : "toggle-btn"}
              onClick={() => setSource("upload")}
              data-tip="Upload your own test files. The sample data is NOT used for uploaded runs."
            >
              <Upload size={15} /> Upload files
            </button>
          </div>
        </div>

        <div className="input-grid">
          {source === "sample" ? (
            // WHY: distinct `key` from the upload input so React remounts rather than
            // reconciling a controlled text field into an uncontrolled file field (which
            // triggers the "controlled/uncontrolled input" warning on toggle).
            <label key="suite-path">
              Suite path
              <input value={suitePath} onChange={(e) => setSuitePath(e.target.value)} required />
            </label>
          ) : (
            <label key="suite-files">
              <span>
                Test files <span className="hint">(.py, .ts, .java, … or a .zip; multiple)</span>
              </span>
              <input
                type="file"
                accept={ACCEPT}
                multiple
                onChange={(e) => setSuiteFiles(Array.from(e.target.files ?? []))}
              />
              {suiteFiles.length > 0 && (
                <span className="hint">{suiteFiles.length} file(s) selected</span>
              )}
            </label>
          )}

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
            <span>
              Coverage target <span className="hint">minimum floor to hold</span>
            </span>
            <div className="flex items-center gap-3 pt-1.5">
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={coveragePct}
                onChange={(e) => setCoveragePct(Number(e.target.value))}
                className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-[var(--surface-3)] accent-[var(--primary)]"
              />
              <span className="w-12 text-right font-mono text-sm font-bold text-[var(--green)]">
                {coveragePct}%
              </span>
            </div>
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

          {/* Optional data sources — only meaningful (and only shown) for uploaded runs. */}
          {source === "upload" && (
            <>
              <label>
                <span>
                  Acceptance criteria <span className="hint">(optional .json)</span>
                </span>
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => setCriteriaFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <label>
                <span>
                  CI history <span className="hint">(optional .json)</span>
                </span>
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => setCiFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <label>
                <span>
                  Expected findings <span className="hint">(optional .json — benchmark)</span>
                </span>
                <input
                  type="file"
                  accept=".json"
                  onChange={(e) => setExpectedFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </>
          )}
        </div>

        {source === "upload" && (
          <p className="hint">
            Uploaded runs analyse only your files — the sample criteria, CI history and expected
            findings are not used. Supply an expected-findings file to get a benchmark score;
            leave criteria / CI empty to run with no reference data.
          </p>
        )}

        {(error || uploadError) && (
          <div className="banner banner-error">{uploadError ?? error}</div>
        )}

        <button className="btn btn-primary" type="submit" disabled={disabled}>
          {disabled ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          {uploading ? "Uploading…" : busy ? "Running…" : "Run Analysis"}
        </button>
      </form>
    </div>
  );
}
