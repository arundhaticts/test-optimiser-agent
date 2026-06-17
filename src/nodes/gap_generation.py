"""
Node 7 — Gap Test Generation.

Drafts a test for each coverage gap, matching the suite's detected conventions. When a
reasoning model is configured it is asked (prompts/gap_generation_prompt) to write the
body; offline it emits a runnable, convention-matching stub. Each generated test is
linked to the criterion it addresses. Increments gen_retry_count (bounds the validation
loop, Blocker #1).
"""

import json
import re

from src.config import REASONING_MODEL
from src.llm import complete, llm_available, load_prompt
from src.observability import audit
from src.tools.tool_wrapper import call_tool, tool_error_entry


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def _draft_test(gap: dict) -> dict:
    cid = gap["criterion_id"]
    name = f"test_{_slug(gap['text'])}"
    code = (
        f"def {name}():\n"
        f'    """Covers {cid}: {gap["text"]}."""\n'
        f'    raise NotImplementedError("TODO: implement gap test for {cid}")\n'
    )
    return {"id": name, "criterion_id": cid, "addresses": gap["text"], "code": code}


def _strip_fences(code: str) -> str:
    m = re.search(r"```(?:python|py)?\s*(.*?)```", code, re.DOTALL)
    return (m.group(1) if m else code).strip()


def _llm_draft_test(gap: dict, conventions: dict) -> dict:
    """Draft a gap test with the reasoning model; raise so call_tool can degrade."""
    context = {"criterion_id": gap["criterion_id"], "criterion_text": gap["text"],
               "conventions": conventions}
    prompt = load_prompt("gap_generation_prompt") + json.dumps(context, indent=2)
    code = _strip_fences(complete(prompt, model=REASONING_MODEL))
    if "def test" not in code:
        from src.tools.tool_wrapper import TransientError
        raise TransientError(f"model produced no test for {gap['criterion_id']}")
    name = f"test_{_slug(gap['text'])}"
    return {"id": name, "criterion_id": gap["criterion_id"],
            "addresses": gap["text"], "code": code}


def gap_generation_node(state) -> dict:
    gaps = state.get("coverage_gaps", [])
    conventions = state.get("conventions", {})
    errors = []
    use_llm = llm_available()

    generated = []
    for g in gaps:
        if use_llm:
            result = call_tool(_llm_draft_test, g, conventions)
            if result["ok"]:
                generated.append(result["data"])
                continue
            errors.append(tool_error_entry(
                "llm:gap_generation", result["error"],
                f"stubbed gap test for {g['criterion_id']}"))
        generated.append(_draft_test(g))

    method = "llm" if use_llm and not errors else (
        "deterministic-fallback" if use_llm else "deterministic")
    retry = state.get("gen_retry_count", 0) + 1
    out = {
        "generated_tests": generated,
        "gen_retry_count": retry,
        "needs_regen": False,
        "audit_log": [audit("gap_generation", "drafted",
                            count=len(generated), attempt=retry, method=method)],
    }
    if errors:
        out["tool_errors"] = errors
    return out
