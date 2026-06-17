"""
Entry point / CLI runner. Keep this thin — all logic lives in src/.

Builds the compiled graph, constructs the initial TestOptimiserState from CLI inputs,
runs it, and at each interrupt() prints the checkpoint payload, reads the human's
decision from stdin (interactive), and resumes. On finish, writes the four output
artifacts to outputs/ and prints a summary.

    python main.py --suite sample_data/sample_suite --goal speed --run-mode interactive
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
    return {
        "project_id": args.project,
        "suite_path": args.suite,
        "optimization_goal": args.goal,
        "coverage_target": args.coverage_target,
        "risk_areas": args.risk_areas.split(",") if args.risk_areas else [],
        "additional_context": "",
        "run_mode": args.run_mode,
        "gen_retry_count": 0,
        "audit_log": [],
        "tool_errors": [],
    }


def _answer_interrupt(payload: dict):
    """Interactive HITL: show the checkpoint and read the decision from stdin.
    Empty input accepts the recommended default."""
    print("\n" + "=" * 70)
    print(f"HITL CHECKPOINT: {payload.get('checkpoint')}")
    print(json.dumps(payload, indent=2)[:2000])
    print("-" * 70)
    if payload["checkpoint"] in ("approve_removals", "approve_tests"):
        raw = input("Approve which ids? (comma-sep, blank = recommended, 'none'): ").strip()
        if raw.lower() == "none":
            return []
        if not raw:
            return payload.get("recommended", [])
        return [x.strip() for x in raw.split(",") if x.strip()]
    input("Press Enter to approve the ranking...")
    return payload.get("prioritised_plan", {})


def run(args) -> dict:
    graph = build_graph()
    config = {"configurable": {"thread_id": args.project}}
    state = graph.invoke(initial_state(args), config=config)

    # Resume through each interrupt until the graph completes.
    while "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        decision = _answer_interrupt(payload)
        # Wrap so an empty (falsy) approval still resumes instead of re-firing the interrupt.
        state = graph.invoke(Command(resume={"__hitl__": decision}), config=config)
    return state["final_outputs"]


def write_outputs(outputs: dict, out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)
    artifacts = {
        "scorecard.json": outputs.get("scorecard", {}),
        "coverage_gap_map.json": outputs.get("coverage_gap_map", {}),
        "redundancy_flakiness_report.json": outputs.get("redundancy_flakiness_report", {}),
        "optimised_plan.json": outputs.get("optimised_plan", {}),
    }
    for name, data in artifacts.items():
        (out_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
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

    configure_logging()
    outputs = run(args)
    out_dir = Path("outputs")
    write_outputs(outputs, out_dir)

    plan = outputs.get("optimised_plan", {})
    print("\n" + "=" * 70)
    print("RUN COMPLETE — artifacts written to outputs/")
    print(f"  proposed removals : {plan.get('proposed', {}).get('removed')}")
    print(f"  projected coverage: {plan.get('projected_coverage')}")
    print(f"  tool errors       : {len(outputs.get('tool_errors', []))}")


if __name__ == "__main__":
    main()
