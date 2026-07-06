"""
Node 1 — Intake & Normalise.

Parses the suite into one internal shape (tools/test_parser via repo_reader), pulls
the entities each test touches with NLP extraction, and writes 'normalised_suite'.
Unparseable tests are ISOLATED (kept + flagged), never silently dropped. Mostly
deterministic — no LLM needed.

Architecture position: Node 1 of 10 — Intake; the pipeline's first node, runs after
START, before coverage.
Called by: the graph (src/graph.py).
Data in: suite_path, raw_suite.
Data out: normalised_suite, conventions, tool_errors[+], audit_log[+].
"""

from src.observability import audit
from src.tools import repo_reader
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.nlp.extraction import extract_entities


def intake_node(state) -> dict:
    """Parse and normalise the test suite into the internal shape.

    Purpose: read the suite via the repo reader, attach NLP-extracted entities to each
        parseable test, isolate unparseable ones, and detect suite conventions.
    Inputs: state — reads suite_path (or raw_suite).
    Outputs: dict with normalised_suite, conventions, audit_log[+]; on an unreadable
        repo instead: normalised_suite=[], tool_errors[+], audit_log[+].
    Side effects: tool call via call_tool(repo_reader.read_tests) (AST parse, file
        reads); calls extract_entities (NLP); appends an audit log entry.
    Called by: the graph (src/graph.py).
    Calls: call_tool, repo_reader.read_tests, repo_reader.detect_conventions,
        extract_entities, tool_error_entry, audit.
    """
    path = state.get("suite_path") or state.get("raw_suite")
    result = call_tool(repo_reader.read_tests, path)

    # WHY: an unreadable repo is fatal in the spec — there is nothing to optimise. Degrade
    # visibly with an empty suite + a halting tool_error rather than crash the run.
    if not result["ok"]:
        # Repo unreadable is fatal in the spec; degrade visibly rather than crash.
        return {
            "normalised_suite": [],
            "tool_errors": [tool_error_entry("repo_reader", result["error"],
                                             "halt: suite unreadable, no plan produced")],
            "audit_log": [audit("intake", "suite_unreadable", error=result["error"])],
        }

    # WHY: split the raw tests into parseable vs unparseable — unparseable tests are
    # counted and kept aside (never silently dropped), parseable ones get enriched.
    raw = result["data"]
    parsed, unparseable = [], []
    for t in raw:
        if t.get("unparseable"):
            unparseable.append(t)
            continue
        # WHY: copy before mutating so we never edit the tool's returned object in place,
        # then attach the entities each test touches (used later for matching/clustering).
        t = dict(t)
        t["entities"] = extract_entities(f"{t.get('name','')} {t.get('docstring','')}")
        parsed.append(t)

    # WHY: derive suite conventions (framework/style) from the parsed tests so gap
    # generation can later draft tests that match.
    conventions = repo_reader.detect_conventions(parsed)
    return {
        "normalised_suite": parsed,
        "conventions": conventions,
        "audit_log": [audit("intake", "normalised_suite",
                            parsed=len(parsed), unparseable=len(unparseable),
                            framework=conventions.get("framework"))],
    }
