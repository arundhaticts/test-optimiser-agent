# Output Reference — Test Optimiser Agent

The agent produces **four deliverables**, written to `outputs/` by the CLI and returned in
the `outputs` object by `POST /runs` / `…/resume` when a run completes. This document
annotates each one field-by-field.

> **These examples reflect the JSON the current code actually emits** (captured from a real
> run against `sample_data/sample_suite`). The shapes in `AGENT_SPEC.md` are an earlier,
> idealised design (e.g. a `confidence` enum, `risk_rank` 1–5, `overlap_pct`); where the
> running code differs, **this file is authoritative for integration** (e.g. building the
> frontend). Differences are called out inline.

Across all outputs: a value is never guessed. When evidence is missing, a score is `null`
and the action is `"insufficient evidence"` (the spec's "insufficient_evidence" confidence,
represented as a null score rather than a separate field).

---

## 1. Test Health Scorecard — `scorecard`

**What it is / when:** produced by the `scoring` node early in the run. Rates the suite
across six quality dimensions. Live runs use Gemini (`method=llm`); offline/degraded runs use
the deterministic rubric (`method=deterministic`). Keyed by dimension name.

```jsonc
{
  "coverage":        { "score": 8, "reason": "Projected coverage 94% but one functional gap.", "action": "Create a test for the 'Password reset email within 60s' gap." },
  "redundancy":      { "score": 7, "reason": "1 identified redundancy cluster.",                "action": "Refactor the identified redundancy cluster." },
  "flakiness":       { "score": 4, "reason": "test_checkout_total is flaky.",                    "action": "Investigate and stabilise test_checkout_total." },
  "speed":           { "score": 5, "reason": "test_payment_gateway is slow.",                    "action": "Optimise test_payment_gateway." },
  "determinism":     { "score": 4, "reason": "A flaky test demonstrates non-determinism.",       "action": "Eliminate the non-deterministic behaviour." },
  "maintainability": { "score": 8, "reason": "Acceptance criteria are present.",                 "action": "Leverage criteria to keep test purpose clear." }
}
```

**Fields (per dimension):**
- `score` — integer **0–10**, or `null`. **0** = critical (act now), **5** = mediocre/mixed,
  **10** = excellent. `null` = **insufficient evidence** (paired with `action: "insufficient
  evidence"`); render it as a neutral "needs data" badge, never as 0.
- `reason` — one-sentence justification grounded in the analysis evidence (counts, named
  tests). Show verbatim.
- `action` — the recommended next step. In a UI this maps to a toggle/CTA: e.g.
  `"merge duplicates"`, `"quarantine flaky"`, `"generate tests for gaps"`, `"re-tier slow
  tests"`, or `"hold"` (no action needed). `"insufficient evidence"` disables the CTA.

**Dimensions:** `coverage`, `redundancy`, `flakiness`, `speed`, `determinism`,
`maintainability` (always all six).

---

## 2. Coverage & Gap Map — `coverage_gap_map`

**What it is / when:** produced by the `coverage` node. Maps acceptance criteria → the tests
that cover them, and lists criteria with no adequate test (the gaps).

```jsonc
{
  "coverage_map": {
    "AC-1": ["test_login_success"],     // criterion → tests linked above CRITERIA_MATCH_THRESHOLD
    "AC-2": ["test_checkout_total"],
    "AC-3": []                          // empty list = no matching test = a gap
  },
  "gaps": [
    {
      "criterion_id": "AC-3",
      "text": "Password reset email is sent within 60s",
      "max_similarity": 0,             // best test↔criterion cosine; 0 = nothing matched at all
      "risk": false                    // true if the criterion falls in a configured risk_area
    }
  ],
  "projected_coverage": 0.82
}
```

**Fields:**
- `coverage_map` — `{criterion_id: [test_id, …]}`. A test is listed when its similarity to the
  criterion is ≥ `CRITERIA_MATCH_THRESHOLD` (default 0.45). An **empty list** = no match above
  threshold = a gap.
- `gaps[]` — one entry per uncovered criterion:
  - `max_similarity` — the best match found (0–1). **`0`** = nothing matched ("no match above
    threshold"); a value like `0.30` means a **partial match** existed but fell below
    `GAP_THRESHOLD`, so it still counts as a gap (good signal that a related test exists and
    could be extended rather than written from scratch).
  - `risk` — boolean. `true` = this gap intersects a configured `risk_area` and should be
    prioritised. *(Spec's `risk_rank` 1–5 is collapsed to this boolean in the current code:
    treat `true` ≈ rank 5 / urgent, `false` ≈ low.)*
- `projected_coverage` — coverage projected for the proposed plan (0–1).

---

## 3. Redundancy & Flakiness Report — `redundancy_flakiness_report`

**What it is / when:** produced by the `redundancy` node. Three lists: near-duplicate
clusters, flaky tests, and slow tests.

```jsonc
{
  "redundancy_flags": [
    {
      "kind": "near_duplicate",
      "cluster": ["test_login_success", "test_login_success_duplicate"],
      "keep": "test_login_success",            // the representative to keep
      "redundant": ["test_login_success_duplicate"],  // the merge/remove candidates
      "evidence": "2 tests cluster above the duplicate threshold.",
      "action": "merge"
    }
  ],
  "flakiness_flags": [
    {
      "test_id": "test_checkout_total",
      "kind": "flaky",
      "fail_rate": 0.36,                        // fails / runs from CI history
      "evidence": "18/50 fails = 36%, >= 10% threshold.",
      "action": "quarantine (reversible) — gated at HITL 1"
    }
  ],
  "slow_flags": [
    {
      "test_id": "test_payment_gateway",
      "kind": "slow",
      "avg_seconds": 42,
      "evidence": "42.0s avg, >= 10.0s threshold.",
      "action": "re-tier out of smoke; candidate for optimisation"
    }
  ]
}
```

**Fields & semantics:**
- **`fail_rate`** = `fails / runs` from the mock/real CI history. Flagged flaky when
  `≥ FLAKY_FAIL_RATE` (default 0.10). `avg_seconds ≥ SLOW_TEST_SECONDS` (10.0) ⇒ slow.
- **`action` / recommendation meanings:**
  - **`merge`** — fold a near-duplicate into the kept representative (reduces upkeep, keeps
    coverage since both cover the same unit).
  - **`quarantine`** — *reversible*: mark a flaky test as non-blocking (moved out of the
    gating path) without deleting it; can be re-enabled once stabilised. Preferred for flaky
    tests.
  - **`remove`** — drop the test entirely; only ever via HITL approval, and never for a
    pinned/risk-area test.
  - **re-tier** (slow) — move out of `smoke` into `full` so the fast tiers stay fast.
- *(The spec's `overlap_pct` is represented here by cluster membership + the `evidence`
  string. Conceptually overlap **0.9** = near-identical tests safe to merge; **0.6** = related
  but distinct — review before merging. The current code clusters above `DUPLICATE_THRESHOLD`
  = 0.80, so anything flagged is in the "safe to merge" range.)*

---

## 4. Optimised Test Plan — `optimised_plan`

**What it is / when:** the headline deliverable, built by `assemble` after all three HITL
approvals. Shows the current suite vs the proposed plan, the tiering, removals, generated
tests, and a summary.

```jsonc
{
  "current": {
    "total_tests": 4,
    "test_ids": ["test_login_success", "test_login_success_duplicate", "test_checkout_total", "test_payment_gateway"]
  },
  "proposed": {
    "removed": ["test_checkout_total", "test_login_success_duplicate"],   // approved at HITL 1
    "merged":  [ { "keep": "test_login_success", "merge": ["test_login_success_duplicate"] } ],
    "tiers":   { "smoke": ["test_login_success"], "regression": [], "full": ["test_payment_gateway"] },
    "generated": [],                  // generated tests the human APPROVED at HITL 3
    "kept": ["test_login_success", "test_payment_gateway"]
  },
  "projected_coverage": 0.82,
  "goal": "speed"
}
```

When a generated gap test is approved at HITL 3, it appears in `proposed.generated` like:

```jsonc
{
  "test_name": "test_password_reset_email_is_sent_within_60s",
  "covers_criterion": "AC-5",
  "code": "import pytest\n...full runnable test source...",
  "validation_status": "passed"        // or "dropped_after_retries"
}
```

**Fields & semantics:**
- **`tiers`** — how the surviving suite is split. Decided by risk + coverage value + the
  `goal`: risk-area/critical tests → `smoke` (run always); criterion-covering tests → `smoke`;
  slow tests → `full` (run less often); everything else → `regression`.
- **`removed` / `merged`** — only contain what the human **approved** at HITL 1. Nothing is
  removed automatically; pinned/risk-area tests can never appear here.
- **`generated`** — only generated tests the human **approved** at HITL 3.
  - `validation_status: "passed"` — the test passed the sandbox syntax/import check.
  - `validation_status: "dropped_after_retries"` — generation/validation failed
    `MAX_GEN_RETRIES` (3) times; the gap is flagged for manual attention rather than shipping a
    broken test (Blocker #1). It is surfaced but not added to the runnable plan.
- *(Where the spec shows `removals[].approved: bool`, the current code only emits
  already-approved items — `approved:false` items are simply absent because a rejected
  recommendation is never written into the plan. A rejected item shows up in the `audit_log`
  /HITL record, not in `proposed`.)*
- *(The spec's `summary` block — `original_count` / `optimised_count` /
  `projected_runtime_seconds` — maps to `current.total_tests` vs `len(proposed.kept)` and
  `projected_coverage` here; explicit projected runtime is not yet computed.)*

---

## Where these come from & how to review a run

- **CLI:** written as `outputs/scorecard.json`, `outputs/coverage_gap_map.json`,
  `outputs/redundancy_flakiness_report.json`, `outputs/optimised_plan.json`.
- **API:** all four nested under the final `outputs` object from `POST /runs` /
  `…/resume`.
- Every run also carries an append-only **`audit_log`** (per-node events) and **`tool_errors`**
  (degraded dependencies) — always check `tool_errors`: an empty list means full-confidence
  results; entries mean some part degraded (e.g. LLM rate-limited → deterministic fallback).
