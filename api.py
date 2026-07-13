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

Architecture position:
    Entrypoint layer — the HTTP bridge over the compiled LangGraph, the sibling of
    main.py's CLI. It owns no agent logic; it exposes the same graph (src/graph.py) as
    a synchronous REST API. A POST blocks until the graph reaches the next interrupt()
    or END, so the client polls/resumes rather than the server streaming.

Called by:
    HTTP clients — primarily the React frontend (Vite dev server on :5173, allowed via
    CORS), but any HTTP client works. Uvicorn hosts the `app` object.

Data in:
    - Request bodies: RunRequest (POST /runs) and ResumeRequest (POST /runs/{id}/resume).
    - Path params: run_id (= thread_id / checkpointer key).
    - Files read indirectly by the graph's nodes/tools (test suite, sample_data/*.json,
      prompts/*.md, .agent_memory/{project}.json).
Data out:
    - JSON HTTP responses: run status + first/next interrupt payload, or the final
      `final_outputs`; state snapshots (audit_log, tool_errors, next) for GET /runs/{id}.
    - Side outputs via the graph: logs/agent.log and updated .agent_memory/{project}.json.
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
# WHY: the React dev frontend runs on a different origin (Vite :5173), so browsers block
# its fetch/XHR unless this backend explicitly allows that origin via CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","http://localhost:5175"],  # Vite dev
    allow_methods=["*"],  # demo backend — accept any method from the allowed origins
    allow_headers=["*"],  # ...and any header (e.g. Content-Type for JSON bodies)
)

GRAPH = build_graph()        # one compiled graph + in-process checkpointer
_RUNS: dict[str, dict] = {}  # run_id -> {status, checkpoint}; in-process run registry

# WHY: eagerly import the heavy Gemini SDK at startup so the latency is paid once here
# rather than on the first POST /runs; wrapped in try/except so an offline/missing-SDK
# environment still boots (the graph falls back to deterministic scoring).
try:
    from src.llm import llm_available
    log.info("warming Gemini SDK | available=%s", llm_available())
except Exception as e:  # noqa: BLE001 — never block startup on warm-up
    log.warning("LLM warm-up skipped: %s", e)


class RunRequest(BaseModel):
    """POST /runs request body — the run parameters that seed the initial state.

    Mirrors the CLI args of main.py: suite path, optional project_id (used as the
    run_id / checkpointer key when supplied), optimisation goal, coverage target,
    protected risk areas, free-text context, and run mode. Field defaults let a client
    kick off a demo run against the sample fixture with an empty body.
    """
    suite_path: str = "sample_data/sample_suite"
    project_id: str | None = None
    optimization_goal: str = "reliability"
    coverage_target: float = DEFAULT_COVERAGE_TARGET
    risk_areas: list[str] = []
    additional_context: str = ""
    run_mode: str = "interactive"


class ResumeRequest(BaseModel):
    """POST /runs/{id}/resume request body — the human's decision for a HITL checkpoint.

    `decision` is deliberately loosely typed (Any) because its shape depends on the
    checkpoint: a list of approved ids for approve_removals/approve_tests, or the
    ranking plan for approve_ranking. It is wrapped as {"__hitl__": decision} before
    being handed to LangGraph's Command(resume=...).
    """
    decision: Any = None


def _config(run_id: str) -> dict:
    """Build the LangGraph config that binds an invoke to a run's checkpoint thread.

    Purpose:
        Produce the {"configurable": {"thread_id": run_id}} config so every invoke for
        a given run_id reads/writes the same checkpointer thread (enabling pause/resume
        across separate HTTP requests).
    Inputs:
        run_id — the run identifier, used directly as the checkpointer thread_id.
    Outputs:
        The config dict passed to GRAPH.invoke / GRAPH.get_state.
    Side effects:
        None (pure).
    Called by:
        start_run, resume_run, get_run.
    Calls:
        Nothing.
    """
    return {"configurable": {"thread_id": run_id}}


def _package(run_id: str, state: dict) -> dict:
    """Turn a graph result into an API response: paused at a checkpoint, or done.

    Purpose:
        Normalise a raw graph state into the wire response and update the in-process
        run registry, distinguishing a run paused at a HITL interrupt from a completed
        run.
    Inputs:
        run_id — the run's id; state — the dict returned by GRAPH.invoke.
    Outputs:
        A response dict: {run_id, status, checkpoint, payload} when awaiting approval,
        or {run_id, status, outputs} when completed.
    Side effects:
        Mutates the module-level _RUNS registry (records status + current checkpoint).
    Called by:
        start_run, resume_run.
    Calls:
        dict.get.
    """
    # WHY: presence of "__interrupt__" is how LangGraph signals the run paused at a HITL
    # checkpoint; its absence means the graph reached END with final_outputs.
    if "__interrupt__" in state:
        # The first pending interrupt's .value is the HITL payload the node emitted.
        payload = state["__interrupt__"][0].value
        # WHY: record the pause in the registry so GET /runs/{id} and resume_run can
        # validate the run and report which checkpoint it's waiting on.
        _RUNS[run_id] = {"status": "awaiting_approval", "checkpoint": payload.get("checkpoint")}
        return {"run_id": run_id, "status": "awaiting_approval",
                "checkpoint": payload.get("checkpoint"), "payload": payload}
    # WHY: no interrupt => the run finished; mark it completed and return the deliverables.
    _RUNS[run_id] = {"status": "completed", "checkpoint": None}
    return {"run_id": run_id, "status": "completed",
            "outputs": state.get("final_outputs", {})}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Bare root has no payload — send visitors to the interactive API docs.

    Purpose:
        Redirect the bare root URL to the Swagger UI so a browser visitor lands somewhere
        useful instead of a 404/empty response.
    Inputs:
        None.
    Outputs:
        A RedirectResponse to /docs.
    Side effects:
        None (pure) beyond returning the redirect.
    Called by:
        HTTP clients (a browser hitting /).
    Calls:
        RedirectResponse.
    """
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    """Liveness probe reporting service status and active-run count.

    Purpose:
        Cheap health check for uptime monitors / the frontend to confirm the backend is
        up and see how many runs it's tracking.
    Inputs:
        None.
    Outputs:
        {"status": "ok", "active_runs": <int>}.
    Side effects:
        Reads the _RUNS registry size; no mutation.
    Called by:
        HTTP clients (monitors, frontend).
    Calls:
        len.
    """
    return {"status": "ok", "active_runs": len(_RUNS)}


@app.post("/runs")
def start_run(req: RunRequest) -> dict:
    """Start a new agent run; block until the first HITL checkpoint or completion.

    Purpose:
        Allocate a run_id, seed the initial state from the request, and invoke the graph
        so it runs up to its first interrupt() (or END), returning that to the client.
    Inputs:
        req — a RunRequest body (suite/goal/coverage_target/risk_areas/context/mode,
        optional project_id).
    Outputs:
        The _package response: awaiting_approval with the first checkpoint payload, or
        completed with outputs (for a run with no interrupts).
    Side effects:
        Logs; invokes the graph (file/LLM/network I/O via nodes; writes a checkpoint
        thread); _package mutates _RUNS.
    Called by:
        HTTP clients (frontend "Run" action).
    Calls:
        uuid.uuid4, GRAPH.invoke, _config, _package, log.info.
    """
    # WHY: honour a caller-supplied project_id (so runs share long-term memory across
    # sessions); otherwise mint a short random run id.
    run_id = req.project_id or f"run-{uuid.uuid4().hex[:8]}"
    # WHY: build the seed TestOptimiserState from the request — same input-layer keys as
    # main.initial_state, with the append-only lists and retry counter initialised.
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
    """Submit a HITL decision for a paused run; block to the next checkpoint or end.

    Purpose:
        Feed the human's decision into the paused graph and continue execution until the
        next interrupt() or END.
    Inputs:
        run_id — the paused run's id (path); req — a ResumeRequest carrying the decision.
    Outputs:
        The _package response: the next checkpoint payload, or the completed outputs.
    Side effects:
        Logs; resumes/invokes the graph (I/O via nodes); _package mutates _RUNS. Raises
        HTTPException 404 for an unknown run_id.
    Called by:
        HTTP clients (frontend HITL "Approve" action).
    Calls:
        GRAPH.invoke, Command, _config, _package, HTTPException, log.info.
    """
    # WHY: guard against resuming a run we never started (or a stale id) with a clear 404.
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="unknown run_id")
    log.info("resume run | run_id=%s", run_id)
    # Wrap the decision so LangGraph always receives a non-empty resume value — an empty
    # list/dict approval would otherwise be dropped and re-fire the same interrupt.
    # The {"__hitl__": ...} envelope is unwrapped by src/hitl/interrupts._decision().
    state = GRAPH.invoke(Command(resume={"__hitl__": req.decision}), config=_config(run_id))
    return _package(run_id, state)


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """Return a current state snapshot for a run (status, next node, audit trail).

    Purpose:
        Let a client poll a run's live state — its status, the next node(s) queued, and
        the append-only audit_log / tool_errors accumulated so far.
    Inputs:
        run_id — the run's id (path).
    Outputs:
        {run_id, status, next, audit_log, tool_errors}.
    Side effects:
        Reads the checkpointer via GRAPH.get_state; no mutation. Raises HTTPException 404
        for an unknown run_id.
    Called by:
        HTTP clients (frontend audit-feed polling).
    Calls:
        GRAPH.get_state, _config, HTTPException, list, dict.get.
    """
    # WHY: only report on runs we know about — an unknown id is a 404, not an empty body.
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="unknown run_id")
    snapshot = GRAPH.get_state(_config(run_id))
    values = snapshot.values or {}  # values is None before the first invoke; default to {}
    # WHY: assemble the polling response — surface status from our registry plus the
    # live append-only trails and pending next-node(s) from the checkpointer snapshot.
    return {
        "run_id": run_id,
        "status": _RUNS[run_id]["status"],
        "next": list(snapshot.next),
        "audit_log": values.get("audit_log", []),
        "tool_errors": values.get("tool_errors", []),
    }
