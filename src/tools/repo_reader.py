"""
Code/repo reader. Used by intake (read tests) and gap generation (match style).

read_tests delegates to the multi-framework parser; read_source reads arbitrary
files; detect_conventions sniffs the suite so generated tests match existing style.
A repo that cannot be read is FATAL — we never produce a partial plan silently.
"""

from pathlib import Path

from src.tools.test_parser import parse
from src.tools.tool_wrapper import FatalError


def read_tests(path) -> list[dict]:
    """Return the internal test representation for a suite path."""
    p = Path(path)
    if not p.exists():
        raise FatalError(f"repo/suite path unreadable: {p}")
    return parse(p)


def read_source(path) -> str:
    """Read a single source file (e.g. for style/convention matching)."""
    p = Path(path)
    if not p.exists():
        raise FatalError(f"source file unreadable: {p}")
    return p.read_text(encoding="utf-8")


def detect_conventions(tests: list[dict]) -> dict:
    """Cheap, deterministic style sniff so gap_generation matches the suite."""
    frameworks = {t.get("framework") for t in tests if t.get("framework")}
    has_docstrings = any(t.get("docstring") for t in tests)
    return {
        "framework": next(iter(frameworks), "pytest"),
        "naming": "test_snake_case",
        "uses_docstrings": has_docstrings,
        "sample_count": len(tests),
    }
