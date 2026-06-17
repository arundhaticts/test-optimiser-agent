"""
Node 1 — Intake & Normalise.

Parses the suite into one internal shape (tools/test_parser via repo_reader), pulls
the entities each test touches with NLP extraction, and writes 'normalised_suite'.
Unparseable tests are ISOLATED (kept + flagged), never silently dropped. Mostly
deterministic — no LLM needed.
"""

from src.observability import audit
from src.tools import repo_reader
from src.tools.tool_wrapper import call_tool, tool_error_entry
from src.nlp.extraction import extract_entities


def intake_node(state) -> dict:
    path = state.get("suite_path") or state.get("raw_suite")
    result = call_tool(repo_reader.read_tests, path)

    if not result["ok"]:
        # Repo unreadable is fatal in the spec; degrade visibly rather than crash.
        return {
            "normalised_suite": [],
            "tool_errors": [tool_error_entry("repo_reader", result["error"],
                                             "halt: suite unreadable, no plan produced")],
            "audit_log": [audit("intake", "suite_unreadable", error=result["error"])],
        }

    raw = result["data"]
    parsed, unparseable = [], []
    for t in raw:
        if t.get("unparseable"):
            unparseable.append(t)
            continue
        t = dict(t)
        t["entities"] = extract_entities(f"{t.get('name','')} {t.get('docstring','')}")
        parsed.append(t)

    conventions = repo_reader.detect_conventions(parsed)
    return {
        "normalised_suite": parsed,
        "conventions": conventions,
        "audit_log": [audit("intake", "normalised_suite",
                            parsed=len(parsed), unparseable=len(unparseable),
                            framework=conventions.get("framework"))],
    }
