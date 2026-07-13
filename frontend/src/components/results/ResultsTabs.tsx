import { useState } from "react";
import type { Outputs } from "../../types";
import HealthScorecard from "./HealthScorecard";
import CoverageMap from "./CoverageMap";
import RedundancyReport from "./RedundancyReport";
import OptimisedPlan from "./OptimisedPlan";
import BenchmarkReport from "./BenchmarkReport";

type Tab = "scorecard" | "coverage" | "redundancy" | "plan" | "benchmark";

export default function ResultsTabs({ outputs }: { outputs: Outputs }) {
  const [tab, setTab] = useState<Tab>("scorecard");

  // WHY: the Benchmark tab only exists when the run was graded against an expected-findings
  // key (demo run vs sample golden, or a benchmark run vs an uploaded key).
  const tabs: { key: Tab; label: string }[] = [
    { key: "scorecard", label: "Health Scorecard" },
    { key: "coverage", label: "Coverage Map" },
    { key: "redundancy", label: "Redundancy & Flakiness" },
    { key: "plan", label: "Optimised Plan" },
    ...(outputs.benchmark ? [{ key: "benchmark" as Tab, label: "Benchmark" }] : []),
  ];

  return (
    <div className="results">
      <div className="tabbar">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? "tab active" : "tab"}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-body">
        {tab === "scorecard" && <HealthScorecard scorecard={outputs.scorecard} />}
        {tab === "coverage" && <CoverageMap data={outputs.coverage_gap_map} />}
        {tab === "redundancy" && <RedundancyReport data={outputs.redundancy_flakiness_report} />}
        {tab === "plan" && <OptimisedPlan plan={outputs.optimised_plan} />}
        {tab === "benchmark" && outputs.benchmark && (
          <BenchmarkReport benchmark={outputs.benchmark} />
        )}
      </div>
    </div>
  );
}
