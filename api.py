"""
FastAPI bridge (demo backend) — thin shell over the compiled graph. No agent logic
lives here; it reuses src/graph.py and drives it over HTTP so the React frontend (or
any client) can run the agent and answer the 3 HITL checkpoints.

Endpoints
  GET  /health                  -> liveness
  POST /runs                    -> start a run; returns run_id + first interrupt or outputs
  POST /runs/{run_id}/resume    -> submit a HITL decision; returns next interrupt or outputs
  GET  /runs/{run_id}           -> current state snapshot (audit_log, status)

The graph is compiled once with a MemorySaver checkpointer keyed by thread_id (= run_id),
so a run pauses at interrupt() and resumes across separate requests. Recommend-only:
nothing is committed or deleted.

Run it:  uvicorn api:app --reload
"""

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command

from src.config import DEFAULT_COVERAGE_TARGET
from src.observability import configure_logging, get_logger
from src.graph import build_graph

configure_logging()
log = get_logger("api")

app = FastAPI(title="Test Optimiser Agent", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev
    allow_methods=["*"],
    allow_headers=["*"],
)

GRAPH = build_graph()        # one compiled graph + in-process checkpointer
_RUNS: dict[str, dict] = {}  # run_id -> {status, checkpoint}

# Warm up the (heavy, ~30s) Gemini SDK import at startup so the first POST /runs
# doesn't pay it on the request path. Harmless no-op when offline / SDK absent.
try:
    from src.llm import llm_available
    log.info("warming Gemini SDK | available=%s", llm_available())
except Exception as e:  # noqa: BLE001 — never block startup on warm-up
    log.warning("LLM warm-up skipped: %s", e)


class RunRequest(BaseModel):
    suite_path: str = "sample_data/sample_suite"
    project_id: str | None = None
    optimization_goal: str = "reliability"
    coverage_target: float = DEFAULT_COVERAGE_TARGET
    risk_areas: list[str] = []
    additional_context: str = ""
    run_mode: str = "interactive"


class ResumeRequest(BaseModel):
    decision: Any = None


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _package(run_id: str, state: dict) -> dict:
    """Turn a graph result into an API response: paused at a checkpoint, or done."""
    if "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        _RUNS[run_id] = {"status": "awaiting_approval", "checkpoint": payload.get("checkpoint")}
        return {"run_id": run_id, "status": "awaiting_approval",
                "checkpoint": payload.get("checkpoint"), "payload": payload}
    _RUNS[run_id] = {"status": "completed", "checkpoint": None}
    return {"run_id": run_id, "status": "completed",
            "outputs": state.get("final_outputs", {})}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Bare root has no payload — send visitors to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "active_runs": len(_RUNS)}


@app.post("/runs")
def start_run(req: RunRequest) -> dict:
    run_id = req.project_id or f"run-{uuid.uuid4().hex[:8]}"
    initial = {
        "project_id": run_id,
        "suite_path": req.suite_path,
        "optimization_goal": req.optimization_goal,
        "coverage_target": req.coverage_target,
        "risk_areas": req.risk_areas,
        "additional_context": req.additional_context,
        "run_mode": req.run_mode,
        "gen_retry_count": 0,
        "audit_log": [], "tool_errors": [],
    }
    log.info("start run | run_id=%s suite=%s mode=%s", run_id, req.suite_path, req.run_mode)
    state = GRAPH.invoke(initial, config=_config(run_id))
    return _package(run_id, state)


@app.post("/runs/{run_id}/resume")
def resume_run(run_id: str, req: ResumeRequest) -> dict:
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="unknown run_id")
    log.info("resume run | run_id=%s", run_id)
    # Wrap the decision so LangGraph always receives a non-empty resume value — an empty
    # list/dict approval would otherwise be dropped and re-fire the same interrupt.
    state = GRAPH.invoke(Command(resume={"__hitl__": req.decision}), config=_config(run_id))
    return _package(run_id, state)


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="unknown run_id")
    snapshot = GRAPH.get_state(_config(run_id))
    values = snapshot.values or {}
    return {
        "run_id": run_id,
        "status": _RUNS[run_id]["status"],
        "next": list(snapshot.next),
        "audit_log": values.get("audit_log", []),
        "tool_errors": values.get("tool_errors", []),
    }
