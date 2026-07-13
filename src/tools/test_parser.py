"""
Multi-framework test parsers.

parse(path) dispatches to per-framework parsers and returns the internal test
representation: a list of dicts {id, name, docstring, framework, file, source}.
Python (pytest/unittest) is parsed via AST (no execution); other languages/frameworks
(JUnit, Jest/Mocha/Vitest/Cypress, Go, RSpec/minitest, NUnit/xUnit) are parsed with
lightweight, dependency-free pattern extractors — enough to recover each test's name and
source span so the deterministic NLP layer (which works on names + docstrings) can match,
cluster, and score them across languages.

Architecture position:
    Integration layer (tools/). Sits behind ``repo_reader.read_tests`` (which is itself
    reached only via ``tool_wrapper.call_tool``). Python is parsed statically via ``ast``
    and NEVER executed; the other extractors are regex/pattern-based and also NEVER execute
    the file.
Called by:
    ``parse`` <- repo_reader.read_tests (<- intake_node).
Data in:  a path to a test file or directory (fixture: ``sample_data/sample_suite/*.py``;
          uploaded suites may mix languages).
Data out: list of test dicts {id, name, docstring, framework, file, source}; unparseable
          Python files get an ``unparseable: True`` marker instead of being dropped.

Extending to a new language: add its file glob(s) to ``_DISCOVERY_GLOBS`` and its extension
to ``_EXTRACTORS`` pointing at a ``_parse_*`` function that returns the standard test dict.
"""

import ast
import re
from pathlib import Path

from src.tools.tool_wrapper import FatalError

# WHY: directory discovery globs, one family per supported framework. Kept as an explicit
# list so adding a language is a one-line change and the set of what-counts-as-a-test-file
# is auditable. The Python patterns (test_*.py / *_test.py) preserve pytest discovery.
_DISCOVERY_GLOBS = [
    "test_*.py", "*_test.py",                     # Python: pytest / unittest
    "*Test.java", "*Tests.java", "Test*.java",    # Java: JUnit
    "*.test.js", "*.test.jsx", "*.test.ts", "*.test.tsx",   # JS/TS: Jest / Vitest / Mocha
    "*.spec.js", "*.spec.jsx", "*.spec.ts", "*.spec.tsx",
    "*.cy.js", "*.cy.ts",                         # Cypress
    "*_test.go",                                  # Go
    "*_spec.rb", "*_test.rb",                     # Ruby: RSpec / minitest
    "*Test.cs", "*Tests.cs",                      # C#: NUnit / xUnit / MSTest
]


def parse(path) -> list[dict]:
    """
    Parse a test file or directory into the internal representation.

    Purpose:  framework-dispatch entry point; walks a directory (or a single file) and
              parses every discovered test across all supported languages.
    Inputs:   ``path`` to a test file or directory.
    Outputs:  flat list of test dicts.
    Side effects: directory globbing + file reads (per-extractor).
    Called by: repo_reader.read_tests.
    Calls:    ``_parse_file``, ``Path.rglob``; raises ``FatalError``.
    """
    p = Path(path)
    # WHY: a missing path is FATAL — call_tool must degrade at once, not retry.
    if not p.exists():
        raise FatalError(f"test path not found: {p}")
    # WHY: a directory is scanned recursively for every framework's test-file pattern
    # (deduped + sorted for stable ordering); a lone path is parsed as a single file.
    if p.is_dir():
        found = {f for glob in _DISCOVERY_GLOBS for f in p.rglob(glob)}
        files = sorted(found)
    else:
        files = [p]
    tests: list[dict] = []
    for f in files:
        tests.extend(_parse_file(f))
    return tests


def _parse_file(file: Path) -> list[dict]:
    """
    Dispatch one file to the extractor for its language, by extension.

    Purpose:  route a single file to the right ``_parse_*`` extractor.
    Inputs:   ``file`` path.
    Outputs:  list of test dicts (empty if the extension is unsupported).
    Side effects: reads the file (via the chosen extractor).
    Called by: ``parse``.
    Calls:    the ``_parse_*`` extractor registered for the file's suffix.
    """
    ext = file.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    # WHY: unknown extension yields no tests (skipped) rather than an error — mixed uploads
    # may contain support files we don't parse.
    if extractor is None:
        return []
    return extractor(file)


def _read(file: Path) -> str:
    """
    Read a source file as text, tolerating odd encodings.

    Purpose:  fetch raw source for pattern extraction without failing on encoding quirks.
    Inputs:   ``file`` path.
    Outputs:  the file's text (undecodable bytes ignored).
    Side effects: reads the file from disk.
    Called by: the non-Python ``_parse_*`` extractors.
    Calls:    ``Path.read_text``.
    """
    # WHY: uploaded files may not be clean UTF-8; ignore undecodable bytes so a single odd
    # character can't abort parsing a whole suite.
    return file.read_text(encoding="utf-8", errors="ignore")


def _record(name: str, framework: str, file: Path, source: str, docstring: str = "") -> dict:
    """
    Build one standard test dict.

    Purpose:  produce the uniform {id, name, docstring, framework, file, source} record all
              extractors return, so downstream nodes are language-agnostic.
    Inputs:   test ``name``, ``framework`` label, ``file`` path, ``source`` snippet, optional
              ``docstring``.
    Outputs:  the test dict.
    Side effects: None (pure).
    Called by: the ``_parse_*`` extractors.
    Calls:    None.
    """
    return {"id": name, "name": name, "docstring": docstring,
            "framework": framework, "file": str(file), "source": source}


def _parse_pytest(file: Path) -> list[dict]:
    """
    Extract `def test_*` functions via AST (never executes the file).

    Purpose:  statically read one Python (pytest/unittest) file into test dicts.
    Inputs:   ``file`` path to a single .py file.
    Outputs:  list of test dicts; a single unparseable-marker dict on SyntaxError.
    Side effects: reads the file from disk (parses only — never runs the tests).
    Called by: ``_parse_file`` (for .py).
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
    # WHY: keep top-level functions named ``test_*`` (the pytest discovery convention),
    # capturing each one's docstring and exact source span.
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
        # WHY: also cover unittest-style classes — `test_*` methods inside a class body —
        # so xUnit-style Python suites aren't missed (top-level pytest suites are unaffected).
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name.startswith("test_"):
                    out.append({
                        "id": f"{node.name}::{sub.name}",
                        "name": sub.name,
                        "docstring": ast.get_docstring(sub) or "",
                        "framework": "pytest",
                        "file": str(file),
                        "source": ast.get_source_segment(src, sub) or "",
                    })
    return out


def _parse_junit(file: Path) -> list[dict]:
    """
    Extract JUnit test methods (Java) by @Test annotation.

    Purpose:  recover Java test names/source spans without a Java parser.
    Inputs:   ``file`` path (.java).
    Outputs:  list of test dicts (framework="junit").
    Side effects: reads the file (pattern match only — never compiled/run).
    Called by: ``_parse_file`` (for .java).
    Calls:    ``re.finditer``, ``_read``, ``_record``.
    """
    src = _read(file)
    out = []
    # WHY: JUnit tests are methods annotated with @Test; find each @Test then the next
    # method name after it (skipping any further annotations/modifiers).
    for m in re.finditer(r"@Test\b", src):
        tail = src[m.end():m.end() + 400]
        nm = re.search(r"(?:public|private|protected|static|\s)+[\w<>\[\], ]+\s+(\w+)\s*\(", tail)
        if nm:
            out.append(_record(nm.group(1), "junit", file, tail.strip()[:200]))
    return out


def _parse_js(file: Path) -> list[dict]:
    """
    Extract Jest/Mocha/Vitest/Cypress tests (JS/TS) by it()/test() titles.

    Purpose:  recover JS/TS test titles/source spans without a JS parser.
    Inputs:   ``file`` path (.js/.jsx/.ts/.tsx/.mjs/.cjs, incl. .cy.* / .spec.* / .test.*).
    Outputs:  list of test dicts (framework="cypress" for .cy.*, else "jest").
    Side effects: reads the file (pattern match only — never executed).
    Called by: ``_parse_file`` (for JS/TS extensions).
    Calls:    ``re.finditer``, ``_read``, ``_record``.
    """
    src = _read(file)
    # WHY: label Cypress specs distinctly (by filename) though the it()/test() grammar is shared.
    framework = "cypress" if ".cy." in file.name else "jest"
    out = []
    # WHY: match it('title', ...) / test('title', ...) with single, double, or template
    # quotes — the near-universal JS test-declaration form across these runners.
    for m in re.finditer(r"""\b(?:it|test)\s*\(\s*(['"`])(.+?)\1""", src):
        title = m.group(2).strip()
        if title:
            out.append(_record(title, framework, file, m.group(0)))
    return out


def _parse_go(file: Path) -> list[dict]:
    """
    Extract Go tests by `func TestXxx(t *testing.T)`.

    Purpose:  recover Go test names/source spans without a Go parser.
    Inputs:   ``file`` path (_test.go).
    Outputs:  list of test dicts (framework="gotest").
    Side effects: reads the file (pattern match only — never executed).
    Called by: ``_parse_file`` (for .go).
    Calls:    ``re.finditer``, ``_read``, ``_record``.
    """
    src = _read(file)
    out = []
    # WHY: Go's testing convention is a top-level `func Test...` — the exact discovery rule
    # `go test` itself uses.
    for m in re.finditer(r"\bfunc\s+(Test\w+)\s*\(", src):
        out.append(_record(m.group(1), "gotest", file, m.group(0)))
    return out


def _parse_ruby(file: Path) -> list[dict]:
    """
    Extract Ruby tests: RSpec `it '...'` and minitest `def test_...`.

    Purpose:  recover Ruby test names/source spans without a Ruby parser.
    Inputs:   ``file`` path (.rb).
    Outputs:  list of test dicts (framework="rspec").
    Side effects: reads the file (pattern match only — never executed).
    Called by: ``_parse_file`` (for .rb).
    Calls:    ``re.finditer``, ``_read``, ``_record``.
    """
    src = _read(file)
    out = []
    # WHY: RSpec examples are `it 'description' do` — capture the human-readable description.
    for m in re.finditer(r"""\bit\s+(['"])(.+?)\1""", src):
        title = m.group(2).strip()
        if title:
            out.append(_record(title, "rspec", file, m.group(0)))
    # WHY: also support minitest's `def test_name` methods so both Ruby styles are covered.
    for m in re.finditer(r"\bdef\s+(test_\w+)", src):
        out.append(_record(m.group(1), "minitest", file, m.group(0)))
    return out


def _parse_csharp(file: Path) -> list[dict]:
    """
    Extract C# tests (NUnit/xUnit/MSTest) by [Test]/[Fact]/[TestMethod] attributes.

    Purpose:  recover C# test method names/source spans without a C# parser.
    Inputs:   ``file`` path (.cs).
    Outputs:  list of test dicts (framework="dotnet").
    Side effects: reads the file (pattern match only — never compiled/run).
    Called by: ``_parse_file`` (for .cs).
    Calls:    ``re.finditer``, ``_read``, ``_record``.
    """
    src = _read(file)
    out = []
    # WHY: the three common .NET frameworks all mark tests with an attribute; find each
    # attribute then the following method name.
    for m in re.finditer(r"\[(?:Test|Fact|Theory|TestMethod)\]", src):
        tail = src[m.end():m.end() + 400]
        nm = re.search(r"(?:public|private|protected|internal|static|async|\s)+"
                       r"(?:Task|void|[\w<>\[\]]+)\s+(\w+)\s*\(", tail)
        if nm:
            out.append(_record(nm.group(1), "dotnet", file, tail.strip()[:200]))
    return out


# WHY: extension -> extractor registry, the single place dispatch is defined. Python maps to
# the AST parser; every other supported language maps to its pattern extractor. Adding a
# language means adding its extension(s) here (and its glob(s) to _DISCOVERY_GLOBS).
_EXTRACTORS = {
    ".py": _parse_pytest,
    ".java": _parse_junit,
    ".js": _parse_js, ".jsx": _parse_js, ".mjs": _parse_js, ".cjs": _parse_js,
    ".ts": _parse_js, ".tsx": _parse_js,
    ".go": _parse_go,
    ".rb": _parse_ruby,
    ".cs": _parse_csharp,
}
