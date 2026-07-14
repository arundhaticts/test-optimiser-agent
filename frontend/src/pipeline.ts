// Derives the live status of each pipeline node from the append-only audit_log,
// tool_errors, and the current run phase. Pure — no React, easy to unit-test.
//
// Node "key" is the audit event `node` name emitted by src/nodes/*.py, so a node
// is Completed once it has appended at least one audit entry.

import type { AuditEntry, Checkpoint, ToolError } from "./types";

export type NodeStatus = "idle" | "running" | "completed" | "degraded" | "awaiting";
export type StepKind = "node" | "gate";

export interface PipelineStep {
  key: string; // audit `node` name
  label: string;
  kind: StepKind;
  checkpoint?: Checkpoint; // set for the 3 HITL gates
}

// The spec's orchestration spine, in execution order, incl. the 3 HITL gates.
export const PIPELINE: PipelineStep[] = [
  { key: "intake", label: "Intake & Normalise", kind: "node" },
  { key: "coverage", label: "Coverage & Gap Analysis", kind: "node" },
  { key: "redundancy", label: "Redundancy & Flakiness", kind: "node" },
  { key: "retrieval", label: "Context Retrieval (RAG)", kind: "node" },
  { key: "scoring", label: "Health Scoring", kind: "node" },
  { key: "hitl_removals", label: "Gate 1 · Approve Removals", kind: "gate", checkpoint: "approve_removals" },
  { key: "prioritisation", label: "Risk Prioritisation", kind: "node" },
  { key: "hitl_priority", label: "Gate 2 · Approve Ranking", kind: "gate", checkpoint: "approve_ranking" },
  { key: "gap_generation", label: "Gap Test Generation", kind: "node" },
  { key: "validation", label: "Static Validation Sandbox", kind: "node" },
  { key: "hitl_generated", label: "Gate 3 · Approve Tests", kind: "gate", checkpoint: "approve_tests" },
  { key: "assemble", label: "Assemble Plan", kind: "node" },
  { key: "report", label: "Render Outputs", kind: "node" },
];

export interface StepState extends PipelineStep {
  status: NodeStatus;
}

/** A degrade touches a step when a tool_error's `tool` names it (e.g. "llm:scoring"). */
function degradedKeys(toolErrors: ToolError[]): Set<string> {
  const keys = new Set<string>();
  for (const e of toolErrors) {
    const tool = (e.tool || "").toLowerCase();
    for (const step of PIPELINE) {
      // "gap_generation" also matches the "gap_gen" node; substring is enough here.
      if (tool.includes(step.key) || (step.key === "gap_generation" && tool.includes("gap"))) {
        keys.add(step.key);
      }
    }
  }
  return keys;
}

export function computeSteps(
  auditLog: AuditEntry[],
  toolErrors: ToolError[],
  opts: { busy: boolean; checkpoint: Checkpoint | null; done: boolean },
): StepState[] {
  const seen = new Set(auditLog.map((e) => e.node));
  const degraded = degradedKeys(toolErrors);
  const firstPending = PIPELINE.find((s) => !seen.has(s.key));

  return PIPELINE.map((step) => {
    let status: NodeStatus = "idle";
    if (opts.checkpoint && step.checkpoint === opts.checkpoint) {
      status = "awaiting"; // agent paused here, awaiting a human decision
    } else if (seen.has(step.key)) {
      status = degraded.has(step.key) ? "degraded" : "completed";
    } else if (opts.busy && !opts.done && firstPending?.key === step.key) {
      status = "running";
    }
    return { ...step, status };
  });
}

/** Headline progress (completed / total) for the sidebar + topbar. */
export function progress(steps: StepState[]): { done: number; total: number } {
  return {
    done: steps.filter((s) => s.status === "completed" || s.status === "degraded").length,
    total: steps.length,
  };
}
