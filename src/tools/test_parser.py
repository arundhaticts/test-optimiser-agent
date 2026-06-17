"""
Multi-framework test parsers.

parse(path) dispatches to per-framework parsers and returns the internal test
representation: a list of dicts {id, name, docstring, framework, file, source}.
Pytest is implemented for the prototype (AST-based, no execution); junit/jest/
cypress are stubbed so the dispatch shape is ready.
"""

import ast
from pathlib import Path

from src.tools.tool_wrapper import FatalError


def parse(path) -> list[dict]:
    """Parse a test file or directory into the internal representation."""
    p = Path(path)
    if not p.exists():
        raise FatalError(f"test path not found: {p}")
    files = sorted(p.rglob("test_*.py")) if p.is_dir() else [p]
    tests: list[dict] = []
    for f in files:
        tests.extend(_parse_pytest(f))
    return tests


def _parse_pytest(file: Path) -> list[dict]:
    """Extract `def test_*` functions via AST (never executes the file)."""
    src = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        # Unparseable — caller (intake) isolates these instead of dropping them.
        return [{"id": file.stem, "name": file.stem, "framework": "pytest",
                 "file": str(file), "source": src, "unparseable": True, "error": str(e)}]
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            out.append({
                "id": node.name,
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "framework": "pytest",
                "file": str(file),
                "source": ast.get_source_segment(src, node) or "",
            })
    return out


# --- Stubs for other frameworks (dispatch shape ready for later) ---
def _parse_junit(file: Path) -> list[dict]:
    raise NotImplementedError("JUnit parser not implemented in the prototype")


def _parse_jest(file: Path) -> list[dict]:
    raise NotImplementedError("Jest parser not implemented in the prototype")


def _parse_cypress(file: Path) -> list[dict]:
    raise NotImplementedError("Cypress parser not implemented in the prototype")
