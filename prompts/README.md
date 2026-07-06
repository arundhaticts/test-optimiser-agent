# `prompts/` — LLM prompt templates

## 1. Purpose

The **prompt templates** that steer Google Gemini for the three tasks where the agent needs
*judgement* rather than deterministic computation: scoring suite health, (reserved) LLM-assisted
prioritisation, and drafting a test for a coverage gap. They are plain Markdown, loaded by
`src/llm.py`.

## 2. Why this folder exists

Keeping prompts as versioned files (not inline strings) lets them be edited, reviewed, and
diffed independently of code, and enforces the NLP-vs-LLM split: only these three steps call the
model, and each has an explicit, auditable instruction with a strict output contract.

## 3. How it fits into the overall architecture

```
 scoring_node        ─ load_prompt("scoring_prompt")        ─▶ Gemini ─▶ strict JSON scorecard
 gap_generation_node ─ load_prompt("gap_generation_prompt") ─▶ Gemini ─▶ runnable test code
 (prioritisation)    ─ prioritisation_prompt (reserved; deterministic tiering used today)
                              │
                              ▼
                     src/llm.py: load_prompt() + complete() + extract_json()
```

## 4. Files inside the folder

`scoring_prompt.md`, `prioritisation_prompt.md`, `gap_generation_prompt.md`.

## 5. Responsibilities of each file

- **`scoring_prompt.md`** — instructs the model to score **6 dimensions** (coverage, redundancy,
  flakiness, speed, determinism, maintainability) using only the supplied evidence. Output:
  strict JSON, one object per dimension `{score: 0–10 | null, reason, action}`; must emit
  `null` / "insufficient evidence" rather than invent data.
- **`gap_generation_prompt.md`** — instructs the model to draft **one runnable test** for an
  uncovered criterion, matching the detected conventions (framework, naming, docstring citing the
  criterion), with a meaningful assertion (never bare `pass`). Output: test code only, no fences.
- **`prioritisation_prompt.md`** — instructs re-tiering (smoke/regression/full) weighted by the
  optimisation goal and risk, returning structured JSON. **Reserved**: the current
  `prioritisation_node` uses deterministic `_tier_for` logic and does not yet call this prompt.

## 6. Inputs

Rendered by the calling node with run context: for scoring, the evidence dict (coverage, gaps,
clusters, flaky/slow, suite size); for gap generation, the criterion + conventions.

## 7. Outputs

Raw model text, parsed downstream by `src/llm.py` (`extract_json` for scoring; fence-stripping
for generated code).

## 8. Dependencies

None at rest (Markdown). Consumed by `src/llm.py` via `load_prompt(name)` (resolves
`prompts/<name>.md`).

## 9. Which folders call/use it

`src/nodes/scoring.py`, `src/nodes/gap_generation.py` (and, when enabled,
`src/nodes/prioritisation.py`) — all through `src/llm.py`.

## 10. Which folders it calls/uses

None — these are static assets.

## 11. Runtime execution flow

```
node → llm.load_prompt("<name>") → format with run evidence → llm.complete(prompt) [via call_tool]
     → scoring: llm.extract_json(text) → scorecard
     → gap gen: strip fences → candidate test → sandbox.validate
If the LLM is unavailable/offline → node uses its deterministic fallback (rubric / stub) instead.
```

## 12. Common debugging locations

- **Scorecard not strict JSON / partial** → wording in `scoring_prompt.md` + `llm.extract_json`.
- **Generated test won't compile** → `gap_generation_prompt.md` (fences/`pass`) + `sandbox.validate`.
- **Prompt file not found** → `load_prompt` name vs the `.md` filename here.
- **Prioritisation prompt seems ignored** → expected; tiering is deterministic today (`_tier_for`).
