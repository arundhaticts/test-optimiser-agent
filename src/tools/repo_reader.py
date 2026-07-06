"""
Code/repo reader. Used by intake (read tests) and gap generation (match style).

read_tests delegates to the multi-framework parser; read_source reads arbitrary
files; detect_conventions sniffs the suite so generated tests match existing style.
A repo that cannot be read is FATAL — we never produce a partial plan silently.

Architecture position:
    Integration layer (tools/). Reached only via ``tool_wrapper.call_tool`` (Blocker #3);
    an unreadable path raises ``FatalError`` so ``call_tool`` degrades on the first
    attempt (no pointless retries).
Called by:
    ``read_tests`` / ``detect_conventions`` <- intake_node; ``read_source`` is available
    for gap-generation style matching.
Data in:  a suite/source path (the sample fixture is ``sample_data/sample_suite/*.py``).
Data out: the internal test representation (list of test dicts), raw source text, or a
          conventions dict.
"""

from pathlib import Path

from src.tools.test_parser import parse
from src.tools.tool_wrapper import FatalError


def read_tests(path) -> list[dict]:
    """
    Return the internal test representation for a suite path.

    Purpose:  entry point used by intake to load the suite off disk.
    Inputs:   ``path`` to a test file or directory.
    Outputs:  list of test dicts (from the parser).
    Side effects: file existence check; delegates the actual read to ``parse``.
    Called by: intake_node (via ``call_tool``).
    Calls:    ``test_parser.parse``; raises ``FatalError``.
    """
    p = Path(path)
    # WHY: an unreadable suite path is FATAL — retrying won't make the files appear, so
    # raise FatalError to make call_tool degrade immediately rather than back off.
    if not p.exists():
        raise FatalError(f"repo/suite path unreadable: {p}")
    return parse(p)


def read_source(path) -> str:
    """
    Read a single source file (e.g. for style/convention matching).

    Purpose:  fetch raw source text (available for gap-generation style matching).
    Inputs:   ``path`` to one source file.
    Outputs:  the file's text content.
    Side effects: reads the file from disk.
    Called by: available for gap-generation style matching.
    Calls:    ``Path.read_text``; raises ``FatalError``.
    """
    p = Path(path)
    # WHY: same FatalError guard — a missing source file cannot be recovered by retrying.
    if not p.exists():
        raise FatalError(f"source file unreadable: {p}")
    return p.read_text(encoding="utf-8")


def detect_conventions(tests: list[dict]) -> dict:
    """
    Cheap, deterministic style sniff so gap_generation matches the suite.

    Purpose:  infer the suite's framework / naming / docstring style so generated tests
              look native to the codebase.
    Inputs:   the parsed ``tests`` list.
    Outputs:  conventions dict {framework, naming, uses_docstrings, sample_count}.
    Side effects: None (pure).
    Called by: intake_node.
    Calls:    None.
    """
    # WHY: derive the dominant framework and whether the suite documents tests, purely
    # from the already-parsed dicts — no I/O, no execution.
    frameworks = {t.get("framework") for t in tests if t.get("framework")}
    has_docstrings = any(t.get("docstring") for t in tests)
    return {
        "framework": next(iter(frameworks), "pytest"),
        "naming": "test_snake_case",
        "uses_docstrings": has_docstrings,
        "sample_count": len(tests),
    }
