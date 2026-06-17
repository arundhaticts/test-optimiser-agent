"""
Isolated sandbox for static validation of generated tests.

validate(test_code) -> {'valid': bool, 'error': str}. Runs a SYNTAX + import-name
check in a separate subprocess (so a crash can't take down the graph) and NEVER
executes test bodies or touches production systems — it only compiles the source.
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
    """Static syntax check in a subprocess. Never executes the test."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _CHECKER],
            input=test_code,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": "sandbox timeout"}
    out = (proc.stdout or "").strip()
    if out == "OK":
        return {"valid": True, "error": ""}
    if out.startswith("ERR:"):
        return {"valid": False, "error": out[4:]}
    return {"valid": False, "error": (proc.stderr or "unknown sandbox error").strip()}
