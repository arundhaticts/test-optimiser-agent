import { useState } from "react";
import type { Outputs } from "../../types";
import HealthScorecard from "./HealthScorecard";
import CoverageMap from "./CoverageMap";
import RedundancyReport from "./RedundancyReport";
import OptimisedPlan from "./OptimisedPlan";

type Tab = "scorecard" | "coverage" | "redundancy" | "plan";

const TABS: { key: Tab; label: string }[] = [
  { key: "scorecard", label: "Health Scorecard" },
  { key: "coverage", label: "Coverage Map" },
  { key: "redundancy", label: "Redundancy & Flakiness" },
  { key: "plan", label: "Optimised Plan" },
];

export default function ResultsTabs({ outputs }: { outputs: Outputs }) {
  const [tab, setTab] = useState<Tab>("scorecard");

  return (
    <div className="results">
      <div className="tabbar">
        {TABS.map((t) => (
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
      </div>
    </div>
  );
}
