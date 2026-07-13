// All HTTP to the FastAPI backend lives here. This is the only place that knows the
// real backend field names (run_id, "awaiting_approval", raw decision shapes); the rest
// of the app uses the normalised types from types.ts.

import axios from "axios";
import type {
  Checkpoint,
  Decision,
  HitlPayload,
  Outputs,
  RunRequest,
  RunResult,
  RunSnapshot,
} from "./types";

const API_BASE = "http://127.0.0.1:8002";

const client = axios.create({ baseURL: API_BASE, timeout: 180_000 });

/** Raw backend response from POST /runs and /resume. */
interface RawRunResponse {
  run_id: string;
  status: "awaiting_approval" | "completed";
  checkpoint?: Checkpoint;
  payload?: HitlPayload;
  outputs?: Outputs;
}

function normalise(raw: RawRunResponse): RunResult {
  if (raw.status === "completed") {
    // outputs carry their own audit_log / tool_errors
    return { status: "completed", threadId: raw.run_id, outputs: raw.outputs as Outputs };
  }
  // checkpoint/payload are always present on an awaiting_approval response
  return {
    status: "interrupted",
    threadId: raw.run_id,
    checkpoint: raw.checkpoint as Checkpoint,
    payload: raw.payload as HitlPayload,
  };
}

function describeError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (err.response) return `Backend ${err.response.status}: ${JSON.stringify(err.response.data)}`;
    if (err.code === "ECONNABORTED") return "Request timed out waiting for the backend.";
    return `Cannot reach backend at ${API_BASE} — is uvicorn running? (${err.message})`;
  }
  return err instanceof Error ? err.message : String(err);
}

export async function checkHealth(): Promise<boolean> {
  try {
    const { data } = await client.get<{ status: string }>("/health");
    return data.status === "ok";
  } catch {
    return false;
  }
}

export async function startRun(req: RunRequest): Promise<RunResult> {
  try {
    const { data } = await client.post<RawRunResponse>("/runs", req);
    return normalise(data);
  } catch (err) {
    throw new Error(describeError(err));
  }
}

/** Resume a paused run. `decision` is the RAW shape the graph expects:
 *  approve_removals -> string[]; approve_ranking -> Tiers; approve_tests -> string[]. */
export async function resumeRun(threadId: string, decision: Decision): Promise<RunResult> {
  try {
    const { data } = await client.post<RawRunResponse>(`/runs/${threadId}/resume`, { decision });
    return normalise(data);
  } catch (err) {
    throw new Error(describeError(err));
  }
}

/** Poll the live audit log / tool errors. Returns null if the run isn't known yet
 *  (the backend only registers a run once its first super-step completes). */
export async function getRun(threadId: string): Promise<RunSnapshot | null> {
  try {
    const { data } = await client.get<{
      run_id: string;
      status: string;
      audit_log?: RunSnapshot["audit_log"];
      tool_errors?: RunSnapshot["tool_errors"];
    }>(`/runs/${threadId}`);
    return {
      threadId: data.run_id,
      status: data.status,
      audit_log: data.audit_log ?? [],
      tool_errors: data.tool_errors ?? [],
    };
  } catch {
    return null; // 404 while the run is still starting — caller ignores
  }
}
