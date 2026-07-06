"""
Multi-framework test parsers.

parse(path) dispatches to per-framework parsers and returns the internal test
representation: a list of dicts {id, name, docstring, framework, file, source}.
Pytest is implemented for the prototype (AST-based, no execution); junit/jest/
cypress are stubbed so the dispatch shape is ready.

Architecture position:
    Integration layer (tools/). Sits behind ``repo_reader.read_tests`` (which is itself
    reached only via ``tool_wrapper.call_tool``). Parses statically via ``ast`` and
    NEVER executes any test code.
Called by:
    ``parse`` <- repo_reader.read_tests (<- intake_node).
Data in:  a path to a test file or directory (fixture: ``sample_data/sample_suite/*.py``).
Data out: list of test dicts {id, name, docstring, framework, file, source}; unparseable
          files get an ``unparseable: True`` marker instead of being dropped.
"""

import ast
from pathlib import Path

from src.tools.tool_wrapper import FatalError


def parse(path) -> list[dict]:
    """
    Parse a test file or directory into the internal representation.

    Purpose:  framework-dispatch entry point; walks a directory (or a single file) and
              parses every discovered test.
    Inputs:   ``path`` to a test file or directory.
    Outputs:  flat list of test dicts.
    Side effects: directory globbing + file reads (via ``_parse_pytest``).
    Called by: repo_reader.read_tests.
    Calls:    ``_parse_pytest``, ``Path.rglob``; raises ``FatalError``.
    """
    p = Path(path)
    # WHY: a missing path is FATAL — call_tool must degrade at once, not retry.
    if not p.exists():
        raise FatalError(f"test path not found: {p}")
    # WHY: a directory is scanned recursively for pytest-named files; a lone path is
    # parsed as a single file.
    files = sorted(p.rglob("test_*.py")) if p.is_dir() else [p]
    tests: list[dict] = []
    for f in files:
        tests.extend(_parse_pytest(f))
    return tests


def _parse_pytest(file: Path) -> list[dict]:
    """
    Extract `def test_*` functions via AST (never executes the file).

    Purpose:  statically read one pytest file into test dicts.
    Inputs:   ``file`` path to a single .py file.
    Outputs:  list of test dicts; a single unparseable-marker dict on SyntaxError.
    Side effects: reads the file from disk (parses only — never runs the tests).
    Called by: ``parse``.
    Calls:    ``ast.parse``, ``ast.get_docstring``, ``ast.get_source_segment``.
    """
    src = file.read_text(encoding="utf-8")
    try:
        # WHY: ast.parse builds the syntax tree WITHOUT importing or executing the file —
        # inspecting the suite must never have side effects.
        tree = ast.parse(src)
    except SyntaxError as e:
        # WHY: unparseable file — return a marker dict (not an exception) so intake
        # isolates the file for review instead of silently dropping its tests.
        return [{"id": file.stem, "name": file.stem, "framework": "pytest",
                 "file": str(file), "source": src, "unparseable": True, "error": str(e)}]
    out = []
    # WHY: walk only top-level statements and keep functions named ``test_*`` — the
    # pytest discovery convention — capturing each one's docstring and exact source span.
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
# WHY: these keep the multi-framework dispatch shape in place but raise
# NotImplementedError — only pytest is supported in the prototype.
def _parse_junit(file: Path) -> list[dict]:
    """
    Purpose:  JUnit parser placeholder (dispatch shape only).
    Inputs:   ``file`` path.  Outputs: N/A.  Side effects: None (pure).
    Called by: reserved for ``parse`` dispatch.  Calls: None.
    """
    raise NotImplementedError("JUnit parser not implemented in the prototype")


def _parse_jest(file: Path) -> list[dict]:
    """
    Purpose:  Jest parser placeholder (dispatch shape only).
    Inputs:   ``file`` path.  Outputs: N/A.  Side effects: None (pure).
    Called by: reserved for ``parse`` dispatch.  Calls: None.
    """
    raise NotImplementedError("Jest parser not implemented in the prototype")


def _parse_cypress(file: Path) -> list[dict]:
    """
    Purpose:  Cypress parser placeholder (dispatch shape only).
    Inputs:   ``file`` path.  Outputs: N/A.  Side effects: None (pure).
    Called by: reserved for ``parse`` dispatch.  Calls: None.
    """
    raise NotImplementedError("Cypress parser not implemented in the prototype")
