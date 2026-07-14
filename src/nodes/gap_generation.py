"""
Node 7 — Gap Test Generation.

Drafts a test for each coverage gap, matching the suite's detected conventions. When a
reasoning model is configured it is asked (prompts/gap_generation_prompt) to write the
body; offline it emits a runnable, convention-matching stub. Each generated test is
linked to the criterion it addresses. Increments gen_retry_count (bounds the validation
loop, Blocker #1).

Architecture position: Node 7 of 10 — Gap Test Generation; runs after HITL 2 (approve
ranking), before validation. Re-entered from validation on retry.
Called by: the graph (src/graph.py).
Data in: coverage_gaps, conventions, gen_retry_count.
Data out: generated_tests, gen_retry_count, needs_regen, tool_errors[+], audit_log[+].
"""

import json
import re

from src.llm import complete, drain_usage, llm_available, load_prompt
from src.observability import audit
from src.tools.tool_wrapper import call_tool, tool_error_entry


def _slug(text: str) -> str:
    """Slugify text into a safe test-function name fragment.

    Purpose: turn criterion text into a lowercase underscore slug (<=40 chars) for use in
        the generated test's function name.
    Inputs: text (str).
    Outputs: the slug string.
    Side effects: None (pure).
    Called by: _draft_test, _llm_draft_test.
    Calls: re.sub.
    """
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def _draft_test(gap: dict) -> dict:
    """Emit a deterministic, convention-matching stub test for a gap.

    Purpose: offline/fallback draft — a runnable stub that raises NotImplementedError,
        linked to the criterion it addresses.
    Inputs: gap (dict with criterion_id, text).
    Outputs: a generated-test dict (id, criterion_id, addresses, code).
    Side effects: None (pure).
    Called by: gap_generation_node.
    Calls: _slug.
    """
    cid = gap["criterion_id"]
    name = f"test_{_slug(gap['text'])}"
    code = (
        f"def {name}():\n"
        f'    """Covers {cid}: {gap["text"]}."""\n'
        f'    raise NotImplementedError("TODO: implement gap test for {cid}")\n'
    )
    return {"id": name, "criterion_id": cid, "addresses": gap["text"], "code": code}


def _strip_fences(code: str) -> str:
    """Strip Markdown code fences from an LLM code response.

    Purpose: pull the code out of a ```python ...``` block if present, else return the
        text as-is (trimmed).
    Inputs: code (raw model output str).
    Outputs: the unfenced, stripped code string.
    Side effects: None (pure).
    Called by: _llm_draft_test.
    Calls: re.search.
    """
    m = re.search(r"```(?:python|py)?\s*(.*?)```", code, re.DOTALL)
    return (m.group(1) if m else code).strip()


def _llm_draft_test(gap: dict, conventions: dict, provider: str | None = None,
                    model: str | None = None) -> dict:
    """Draft a gap test with the reasoning model; raise so call_tool can degrade.

    Purpose: prompt the reasoning model to write a convention-matching test for a gap.
    Inputs: gap (dict with criterion_id, text); conventions (suite style dict).
    Outputs: a generated-test dict (id, criterion_id, addresses, code).
    Side effects: LLM call (load_prompt + complete); raises TransientError if the output
        contains no test so call_tool degrades to the stub. Invoked via call_tool.
    Called by: gap_generation_node (via call_tool).
    Calls: load_prompt, complete, _strip_fences, _slug, json.dumps.
    """
    context = {"criterion_id": gap["criterion_id"], "criterion_text": gap["text"],
               "conventions": conventions}
    prompt = load_prompt("gap_generation_prompt") + json.dumps(context, indent=2)
    code = _strip_fences(complete(prompt, provider=provider, model=model))
    # WHY: guard against a non-test response — no test def means degrade to the stub.
    if "def test" not in code:
        from src.tools.tool_wrapper import TransientError
        raise TransientError(f"model produced no test for {gap['criterion_id']}")
    name = f"test_{_slug(gap['text'])}"
    return {"id": name, "criterion_id": gap["criterion_id"],
            "addresses": gap["text"], "code": code}


def gap_generation_node(state) -> dict:
    """Draft one test per coverage gap (LLM when available, else stub).

    Purpose: generate a test for each gap, using the reasoning model when configured and
        falling back to a deterministic stub per-gap on failure; increment the loop guard.
    Inputs: state — reads coverage_gaps, conventions, gen_retry_count.
    Outputs: dict with generated_tests, gen_retry_count (++), needs_regen=False,
        audit_log[+], and tool_errors[+] when any LLM draft was stubbed.
    Side effects: may make LLM calls (via call_tool(_llm_draft_test)); appends an audit
        log entry.
    Called by: the graph (src/graph.py; also re-entered on validation retry).
    Calls: llm_available, call_tool(_llm_draft_test), _draft_test, tool_error_entry, audit.
    """
    gaps = state.get("coverage_gaps", [])
    conventions = state.get("conventions", {})
    provider = state.get("provider")
    model = state.get("model")
    errors = []
    use_llm = llm_available(provider)

    generated = []
    # WHY: per gap, prefer the LLM draft; on any LLM failure record a tool_error and fall
    # through to the deterministic stub so every gap still gets a draft.
    for g in gaps:
        if use_llm:
            result = call_tool(_llm_draft_test, g, conventions, provider, model)
            if result["ok"]:
                generated.append(result["data"])
                continue
            errors.append(tool_error_entry(
                "llm:gap_generation", result["error"],
                f"stubbed gap test for {g['criterion_id']}"))
        # WHY: reached when no LLM, or the LLM draft failed for this gap.
        generated.append(_draft_test(g))

    # WHY: label the method for the audit trail — pure llm only if used and no fallbacks.
    method = "llm" if use_llm and not errors else (
        "deterministic-fallback" if use_llm else "deterministic")
    # WHY: increment gen_retry_count (Blocker #1) — route_after_validation caps the
    # gap_gen/validation loop at MAX_GEN_RETRIES using this counter.
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
    # WHY: attach token usage from the LLM drafts this node made (empty on the
    # deterministic path) so it accumulates into state["llm_usage"] like audit_log.
    out["llm_usage"] = drain_usage()
    return out
