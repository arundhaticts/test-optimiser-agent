"""
Entry point / CLI runner.

MUST CONTAIN:
- Argument parsing (--suite path, --project, --goal, --coverage-target, --run-mode).
- Build the compiled graph by calling src/graph.py.
- Construct the initial TestOptimiserState from the CLI inputs.
- Invoke the graph; when it hits an interrupt(), print the payload, collect the
  human's answer from stdin (interactive mode), and resume the graph.
- On finish, write the four output artifacts and print a summary.
This is the only file a user runs directly; keep it thin — all logic lives in src/.
"""
