// TypeScript shapes for the Test Optimiser Agent API.
//
// These match the ACTUAL backend (api.py / src/hitl/interrupts.py / docs/OUTPUTS.md),
// not the idealised contract — see api.ts for where backend field names are adapted.

export type Goal = "speed" | "coverage" | "reliability" | "cost";
export type RunMode = "interactive" | "automated";
export type Checkpoint = "approve_removals" | "approve_ranking" | "approve_tests";

export interface RunRequest {
  suite_path: string;
  project_id: string;
  optimization_goal: Goal;
  coverage_target: number; // 0.0–1.0
  risk_areas: string[];
  run_mode: RunMode;
}

// ---------- HITL payloads (from src/hitl/interrupts.py) ----------

export interface RemovalCandidate {
  test_id: string;
  reason: string; // "flaky" | "near-duplicate"
  evidence: string;
  kind: string; // recommended action: "quarantine" | "merge"
  pinned: boolean;
}

export interface RemovalsPayload {
  checkpoint: "approve_removals";
  candidates: RemovalCandidate[];
  recommended: string[];
  note?: string;
}

export interface Tiers {
  smoke: string[];
  regression: string[];
  full: string[];
}

export interface RankingRow {
  test_id: string;
  tier: keyof Tiers;
  reason: string;
}

export interface RankingPayload {
  checkpoint: "approve_ranking";
  prioritised_plan: { tiers: Tiers; ranking: RankingRow[]; goal: string };
  projected_coverage: number;
  note?: string;
}

export interface GeneratedTest {
  id: string;
  criterion_id: string;
  addresses: string;
  code: string;
  valid?: boolean;
}

export interface DroppedTest {
  id: string;
  criterion_id?: string;
  reason?: string;
}

export interface TestsPayload {
  checkpoint: "approve_tests";
  generated_tests: GeneratedTest[];
  dropped: DroppedTest[];
  recommended: string[];
  note?: string;
}

export type HitlPayload = RemovalsPayload | RankingPayload | TestsPayload;

// ---------- Decision shapes posted back (raw, as the graph expects) ----------

export type RemovalsDecision = string[]; // approved test ids
export type RankingDecision = Tiers; // approved tiering
export type TestsDecision = string[]; // approved generated test ids
export type Decision = RemovalsDecision | RankingDecision | TestsDecision;

// ---------- Audit / errors ----------

export interface AuditEntry {
  ts?: string;
  node: string;
  event: string;
  details?: Record<string, unknown>;
}

export interface ToolError {
  tool: string;
  error: string;
  degrade?: string;
}

// ---------- Output deliverables (docs/OUTPUTS.md is authoritative) ----------

export interface ScorecardEntry {
  score: number | null; // null = insufficient evidence (render "Needs data", never 0)
  reason: string;
  action: string;
}
export type Scorecard = Record<string, ScorecardEntry>;

export interface CoverageGap {
  criterion_id: string;
  text: string;
  max_similarity: number;
  risk: boolean;
  addressed_by?: string; // id of an approved generated test that now drafts a fix
}
export interface CoverageGapMap {
  coverage_map: Record<string, string[]>;
  gaps: CoverageGap[];
  projected_coverage: number;
}

export interface RedundancyFlag {
  kind: string;
  cluster: string[];
  keep: string;
  redundant: string[];
  evidence: string;
  action: string;
}
export interface FlakinessFlag {
  test_id: string;
  kind: string;
  fail_rate: number;
  evidence: string;
  action: string;
}
export interface SlowFlag {
  test_id: string;
  kind: string;
  avg_seconds: number;
  evidence: string;
  action: string;
}
export interface RedundancyFlakinessReport {
  redundancy_flags: RedundancyFlag[];
  flakiness_flags: FlakinessFlag[];
  slow_flags: SlowFlag[];
}

export interface MergeEntry {
  keep: string;
  merge: string[];
}
export interface OptimisedPlan {
  current: { total_tests: number; test_ids: string[] };
  proposed: {
    removed: string[];
    merged: MergeEntry[];
    tiers: Tiers;
    generated: string[];
    kept: string[];
  };
  projected_coverage: number;
  goal: string;
}

export interface Outputs {
  scorecard: Scorecard;
  coverage_gap_map: CoverageGapMap;
  redundancy_flakiness_report: RedundancyFlakinessReport;
  optimised_plan: OptimisedPlan;
  audit_log?: AuditEntry[];
  tool_errors?: ToolError[];
}

// ---------- Normalised API result (adapted from the raw backend response) ----------

export type RunResult =
  | { status: "interrupted"; threadId: string; checkpoint: Checkpoint; payload: HitlPayload }
  | { status: "completed"; threadId: string; outputs: Outputs };

export interface RunSnapshot {
  threadId: string;
  status: string;
  audit_log: AuditEntry[];
  tool_errors: ToolError[];
}
