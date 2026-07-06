"""
Entry point / CLI runner. Keep this thin — all logic lives in src/.

Builds the compiled graph, constructs the initial TestOptimiserState from CLI inputs,
runs it, and at each interrupt() prints the checkpoint payload, reads the human's
decision from stdin (interactive), and resumes. On finish, writes the four output
artifacts to outputs/ and prints a summary.

    python main.py --suite sample_data/sample_suite --goal speed --run-mode interactive

Architecture position:
    Entrypoint layer — the CLI driver over the compiled LangGraph. It sits above
    src/graph.py (which owns all nodes, routing, and the checkpointer) and holds no
    agent logic of its own. Its only jobs are: parse CLI args, seed the initial state,
    invoke the graph, service the three HITL interrupts from stdin, and persist the
    four deliverables. The parallel HTTP entrypoint is api.py.

Called by:
    A human operator from the shell (`python main.py ...`); i.e. the `if __name__ ==
    "__main__"` guard invokes main().

Data in:
    - CLI args: --suite, --project, --goal, --coverage-target, --risk-areas, --run-mode.
    - stdin: the human's approval decisions at each of the three HITL checkpoints.
    - Files read indirectly by the graph's nodes/tools (the test suite under --suite,
      sample_data/*.json, prompts/*.md, .agent_memory/{project}.json).

Data out:
    - The graph's `final_outputs` dict, written as four JSON artifacts under outputs/
      (scorecard.json, coverage_gap_map.json, redundancy_flakiness_report.json,
      optimised_plan.json).
    - A human-readable run summary printed to stdout; audit lines to logs/agent.log.
"""

import argparse
import json
from pathlib import Path

from langgraph.types import Command

from src.config import DEFAULT_COVERAGE_TARGET
from src.observability import configure_logging, get_logger
from src.graph import build_graph

log = get_logger("main")


def initial_state(args) -> dict:
    """Build the seed TestOptimiserState dict from parsed CLI args.

    Purpose:
        Translate CLI arguments into the initial state the graph expects on its first
        invoke, including the append-only accumulators seeded empty and the retry
        counter seeded to zero.
    Inputs:
        args — the argparse.Namespace produced by main() (project, suite, goal,
        coverage_target, risk_areas, run_mode).
    Outputs:
        A dict of initial TestOptimiserState keys (no working/decision/result keys yet;
        those are filled in by nodes downstream).
    Side effects:
        None (pure).
    Called by:
        run().
    Calls:
        str.split (to turn the comma-separated --risk-areas into a list).
    """
    # WHY: seed exactly the input-layer keys plus the two append-only accumulators
    # (audit_log, tool_errors) and the generation-loop guard (gen_retry_count) so every
    # node downstream can read/append without KeyErrors.
    return {
        "project_id": args.project,
        "suite_path": args.suite,
        "optimization_goal": args.goal,
        "coverage_target": args.coverage_target,
        "risk_areas": args.risk_areas.split(",") if args.risk_areas else [],
        "additional_context": "",
        "run_mode": args.run_mode,
        "gen_retry_count": 0,  # generation-loop guard; capped later at MAX_GEN_RETRIES
        "audit_log": [],       # append-only (Annotated[list, add]) — never overwrite
        "tool_errors": [],     # append-only degrade trail from call_tool failures
    }


def _answer_interrupt(payload: dict):
    """Interactive HITL: show the checkpoint and read the decision from stdin.
    Empty input accepts the recommended default.

    Purpose:
        Render one HITL checkpoint payload to the operator and collect their decision,
        so run() can resume the paused graph. Handles the two id-approval checkpoints
        (approve_removals / approve_tests) and the ranking checkpoint distinctly.
    Inputs:
        payload — the interrupt().value dict emitted by a HITL node; carries
        `checkpoint`, and (per checkpoint) `recommended` and/or `prioritised_plan`.
    Outputs:
        The human decision: a list of approved ids for the id-approval checkpoints, or
        the prioritised_plan dict for the ranking checkpoint.
    Side effects:
        Console I/O — prints the payload and blocks on input() reading stdin.
    Called by:
        run().
    Calls:
        print, json.dumps, input.
    """
    # WHY: frame the checkpoint clearly for the operator and truncate the payload dump
    # so a large plan doesn't flood the terminal.
    print("\n" + "=" * 70)
    print(f"HITL CHECKPOINT: {payload.get('checkpoint')}")
    print(json.dumps(payload, indent=2)[:2000])
    print("-" * 70)
    # WHY: the two removal/generation checkpoints gate a set of ids, so we collect a
    # list; the ranking checkpoint only needs an acknowledgement of the plan.
    if payload["checkpoint"] in ("approve_removals", "approve_tests"):
        raw = input("Approve which ids? (comma-sep, blank = recommended, 'none'): ").strip()
        # WHY: "none" is an explicit reject-all — distinct from blank, which accepts the
        # agent's recommendation.
        if raw.lower() == "none":
            return []
        if not raw:
            return payload.get("recommended", [])
        # Split the comma-separated ids, trimming whitespace and dropping empties.
        return [x.strip() for x in raw.split(",") if x.strip()]
    # WHY: ranking approval is a simple accept — echo back the plan the agent proposed.
    input("Press Enter to approve the ranking...")
    return payload.get("prioritised_plan", {})


def run(args) -> dict:
    """Compile the graph, run it, and drive the interrupt/resume loop to completion.

    Purpose:
        Own the full CLI run: build the compiled graph, seed state, invoke, and service
        every HITL interrupt from stdin until the graph reaches END, then hand back the
        deliverables.
    Inputs:
        args — the argparse.Namespace of CLI options.
    Outputs:
        The graph's `final_outputs` dict (the four deliverables) at completion.
    Side effects:
        Compiles/invokes the LangGraph (which performs the agent's file/LLM/network I/O
        and logging via its nodes); console I/O via _answer_interrupt.
    Called by:
        main().
    Calls:
        build_graph, initial_state, graph.invoke, _answer_interrupt, Command.
    """
    graph = build_graph()
    # thread_id keys the checkpointer so the paused run can be resumed across invokes.
    config = {"configurable": {"thread_id": args.project}}
    state = graph.invoke(initial_state(args), config=config)

    # WHY: interrupt-resume loop — the graph pauses at each interrupt() and returns a
    # state carrying "__interrupt__"; we answer it and re-invoke until it's absent
    # (graph reached END). This is what makes the three HITL checkpoints interactive.
    while "__interrupt__" in state:
        # The first pending interrupt's .value is the payload the HITL node emitted.
        payload = state["__interrupt__"][0].value
        decision = _answer_interrupt(payload)
        # Wrap so an empty (falsy) approval still resumes instead of re-firing the interrupt.
        # The {"__hitl__": ...} envelope is unwrapped by src/hitl/interrupts._decision().
        state = graph.invoke(Command(resume={"__hitl__": decision}), config=config)
    return state["final_outputs"]


def write_outputs(outputs: dict, out_dir: Path) -> None:
    """Persist the four deliverables from `final_outputs` to JSON files on disk.

    Purpose:
        Materialise the graph's in-memory deliverables as the four artifact files the
        run is expected to produce.
    Inputs:
        outputs — the `final_outputs` dict; out_dir — target directory (outputs/).
    Outputs:
        None (returns nothing).
    Side effects:
        Filesystem — creates out_dir if missing and writes four JSON files into it.
    Called by:
        main().
    Calls:
        Path.mkdir, json.dumps, Path.write_text.
    """
    out_dir.mkdir(exist_ok=True)
    # WHY: map each deliverable to its filename, defaulting to {} so a partial run
    # still writes valid (empty) JSON rather than crashing on a missing key.
    artifacts = {
        "scorecard.json": outputs.get("scorecard", {}),
        "coverage_gap_map.json": outputs.get("coverage_gap_map", {}),
        "redundancy_flakiness_report.json": outputs.get("redundancy_flakiness_report", {}),
        "optimised_plan.json": outputs.get("optimised_plan", {}),
    }
    # WHY: one write per artifact — indent for human-readable diffs, utf-8 for portability.
    for name, data in artifacts.items():
        (out_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    """CLI entrypoint: parse args, configure logging, run the agent, write outputs.

    Purpose:
        Wire the whole CLI flow together — argument parsing, one-time logging setup,
        the graph run (with interactive HITL), artifact persistence, and a summary.
    Inputs:
        None directly; reads sys.argv via argparse.
    Outputs:
        None (returns nothing).
    Side effects:
        Console I/O; configures logging (creates logs/); runs the graph (file/LLM/network
        I/O via nodes); writes the four artifacts to outputs/.
    Called by:
        The `if __name__ == "__main__"` guard (the shell operator).
    Calls:
        argparse.ArgumentParser, configure_logging, run, write_outputs, print.
    """
    # WHY: define the CLI surface — required suite path plus the tunable run parameters,
    # with choices constraining goal/run-mode to the values the graph understands.
    p = argparse.ArgumentParser(description="Test Optimiser Agent")
    p.add_argument("--suite", required=True, help="path to the test suite")
    p.add_argument("--project", default="default", help="project id (memory key)")
    p.add_argument("--goal", default="reliability",
                   choices=["speed", "coverage", "reliability", "cost"])
    p.add_argument("--coverage-target", type=float, default=DEFAULT_COVERAGE_TARGET,
                   dest="coverage_target")
    p.add_argument("--risk-areas", default="", dest="risk_areas",
                   help="comma-separated risk areas to protect")
    p.add_argument("--run-mode", default="interactive",
                   choices=["interactive", "automated"], dest="run_mode")
    args = p.parse_args()

    # WHY: set up rotating file logging once, before any node runs, so the whole run's
    # audit trail lands in logs/agent.log.
    configure_logging()
    outputs = run(args)
    out_dir = Path("outputs")
    write_outputs(outputs, out_dir)

    # WHY: print a concise post-run summary so the operator sees the headline results
    # (removals, projected coverage, degrade count) without opening the JSON files.
    plan = outputs.get("optimised_plan", {})
    print("\n" + "=" * 70)
    print("RUN COMPLETE — artifacts written to outputs/")
    print(f"  proposed removals : {plan.get('proposed', {}).get('removed')}")
    print(f"  projected coverage: {plan.get('projected_coverage')}")
    print(f"  tool errors       : {len(outputs.get('tool_errors', []))}")


if __name__ == "__main__":
    # WHY: run as a script only — importing this module (e.g. in tests) must not launch.
    main()
