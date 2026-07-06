"""
Isolated sandbox for static validation of generated tests.

validate(test_code) -> {'valid': bool, 'error': str}. Runs a SYNTAX + import-name
check in a separate subprocess (so a crash can't take down the graph) and NEVER
executes test bodies or touches production systems — it only compiles the source.

Architecture position:
    Integration layer (tools/). The only place the agent spawns a subprocess. Used by
    the validation node to gate LLM-drafted tests before a human approves them; it
    compiles the source (syntax check) but never runs the tests or hits production.
Called by:
    ``validate`` <- validation_node.
Data in:   generated test source code + an optional timeout.
Data out:  ``{'valid': bool, 'error': str}``.
"""

import subprocess
import sys

# Tiny checker run in a child process: compile the source (syntax) without executing
# it. Reads code from stdin so there are no quoting/escaping problems.
_CHECKER = (
    "import sys\n"
    "src = sys.stdin.read()\n"
    "try:\n"
    "    compile(src, '<generated_test>', 'exec')\n"
    "    print('OK')\n"
    "except SyntaxError as e:\n"
    "    print('ERR:' + str(e))\n"
)


def validate(test_code: str, timeout: float = 10.0) -> dict:
    """
    Static syntax check in a subprocess. Never executes the test.

    Purpose:  gate a generated test on compilability before human approval.
    Inputs:   ``test_code`` (source), ``timeout`` seconds for the child process.
    Outputs:  ``{'valid': bool, 'error': str}``.
    Side effects: spawns a Python subprocess (``subprocess.run``); no network, no writes,
                  never executes the test body.
    Called by: validation_node.
    Calls:    ``subprocess.run``.
    """
    try:
        # WHY: run the checker in a child process and feed the source on stdin — a crash
        # in the child can't take down the graph, and stdin avoids all quoting/escaping.
        proc = subprocess.run(
            [sys.executable, "-c", _CHECKER],
            input=test_code,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # WHY: a hung/slow compile is treated as invalid rather than blocking the run.
        return {"valid": False, "error": "sandbox timeout"}
    out = (proc.stdout or "").strip()
    # WHY: the checker prints exactly 'OK' on a clean compile.
    if out == "OK":
        return {"valid": True, "error": ""}
    # WHY: on SyntaxError the checker prints 'ERR:<message>'; strip the 4-char 'ERR:'
    # prefix to surface just the error text.
    if out.startswith("ERR:"):
        return {"valid": False, "error": out[4:]}
    # WHY: any other outcome (no recognised stdout) falls back to the child's stderr.
    return {"valid": False, "error": (proc.stderr or "unknown sandbox error").strip()}
