# Configuration Reference — Test Optimiser Agent

Every tunable in [../src/config.py](../src/config.py), what it controls, and how to tune it.
**No magic numbers live in nodes** — they all come from here, so this file is the complete
list of behavioural knobs.

> Thresholds can be overridden via environment variables where noted; otherwise edit
> `src/config.py`. After any change, re-run the golden eval set (see the warning at the end).

---

## 1. Reference table

### Loops & coverage

| Variable | Default | Controls | Raise it → / Lower it → |
|----------|---------|----------|--------------------------|
| `MAX_GEN_RETRIES` | `3` | Cap on the validation→gap_generation loop before falling back to `drop_failing`. | **Raise:** more attempts to fix a broken generated test (slower, more LLM cost). **Lower:** gives up sooner. **Do not remove** — it guarantees the loop terminates (Blocker #1). |
| `DEFAULT_COVERAGE_TARGET` | `0.80` | The hard coverage floor the gate enforces; a change set projected below this routes to `revise`. | **Raise:** stricter — fewer removals allowed, more tests kept. **Lower:** permits more aggressive trimming, more coverage risk. |

### Semantic similarity (cosine, 0–1)

| Variable | Default | Controls | Raise it → / Lower it → |
|----------|---------|----------|--------------------------|
| `CRITERIA_MATCH_THRESHOLD` | `0.45` | Minimum similarity to link a test to an acceptance criterion. | **Raise:** only strong matches count → more criteria look uncovered (more gaps). **Lower:** loose matching → fewer gaps, more false links. |
| `DUPLICATE_THRESHOLD` | `0.80` | Minimum similarity to group two tests as near-duplicates. | **Raise:** only near-identical tests flagged (fewer duplicates). **Lower:** flags loosely-similar tests (risk of over-merging distinct tests). |
| `GAP_THRESHOLD` | `0.45` | A criterion whose best test-match is below this is a coverage gap. | **Raise:** more criteria count as gaps (more tests generated). **Lower:** fewer gaps. |

### Flakiness & speed

| Variable | Default | Controls | Raise it → / Lower it → |
|----------|---------|----------|--------------------------|
| `FLAKY_FAIL_RATE` | `0.10` | `fails/runs ≥ this` ⇒ flaky. | **Raise:** only very unreliable tests flagged. **Lower:** flags mildly unstable tests too. |
| `SLOW_TEST_SECONDS` | `10.0` | `avg_seconds ≥ this` ⇒ slow. | **Raise:** only the slowest tests flagged. **Lower:** flags more tests as slow → more re-tiering to `full`. |

### Coverage model (projection used by the gate)

| Variable | Default | Controls |
|----------|---------|----------|
| `COVERAGE_BASE` | `0.70` | Baseline projected coverage. |
| `COVERAGE_PER_UNIT` | `0.06` | Coverage credited per distinct unit still covered. Removing a redundant duplicate (shared unit) costs nothing; removing a unique test costs coverage — which is exactly what the floor gate protects. |
| `COVERAGE_CAP` | `0.98` | Upper bound on projected coverage. |

### Tool retry / degrade (Blocker #3)

| Variable | Default | Controls | Raise it → / Lower it → |
|----------|---------|----------|--------------------------|
| `TOOL_RETRIES` | `3` | Attempts per external call in `call_tool` before degrading. | **Raise:** more resilient to flaky deps (slower failures). **Lower:** fails/degrades faster. |
| `BACKOFF_BASE` | `2` | Exponential backoff base: wait `BACKOFF_BASE ** attempt` seconds. | **Raise:** longer waits between retries. **Lower:** snappier retries, more pressure on the dependency. |

### Models & providers (from env)

| Variable | Default | Controls |
|----------|---------|----------|
| `GEMINI_API_KEY` | — | Gemini auth (also reads `GOOGLE_API_KEY`). Unset ⇒ `OFFLINE_MODE`. |
| `REASONING_MODEL` | `gemini-2.5-flash` | Scoring + gap-test generation (the judgement calls). |
| `FAST_MODEL` | `gemini-2.5-flash` | Lighter/mechanical passes. |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model (only when `EMBED_ALLOW_DOWNLOAD=1`). |
| `OFFLINE_MODE` | `0` | `1` forces deterministic scoring/NLP even with a key. |
| `EMBED_ALLOW_DOWNLOAD` | `0` | `1` enables real embeddings (downloads model once); `0` uses deterministic hashing vectors. |
| `SPACY_NER` | `0` | `1` enables spaCy NER; `0` uses deterministic keyword extraction. |

---

## 2. Tuning guide by `optimization_goal`

The goal is passed at run time (`--goal` / `optimization_goal`). It steers prioritisation;
these threshold nudges reinforce it.

- **`speed`** — minimise runtime. Lower `SLOW_TEST_SECONDS` (e.g. `5.0`) so more slow tests
  are re-tiered out of smoke; consider lowering `DUPLICATE_THRESHOLD` slightly to merge more
  near-duplicates. Keep `DEFAULT_COVERAGE_TARGET` where it is so speed doesn't sacrifice the
  floor.
- **`coverage`** — protect/expand coverage. Raise `DEFAULT_COVERAGE_TARGET` (e.g. `0.90`);
  raise `GAP_THRESHOLD` and `CRITERIA_MATCH_THRESHOLD` so weak matches count as gaps and more
  tests get generated. Keep `DUPLICATE_THRESHOLD` high to avoid merging away real coverage.
- **`reliability`** — kill flakiness. Lower `FLAKY_FAIL_RATE` (e.g. `0.05`) to catch mildly
  unstable tests; keep `MAX_GEN_RETRIES` at 3 so regenerated tests are still validated. Slow
  thresholds matter less here.
- **`cost`** — minimise LLM/CI spend. Keep `EMBED_ALLOW_DOWNLOAD=0` and `SPACY_NER=0`
  (deterministic, no downloads); consider lowering `TOOL_RETRIES` to fail fast; raise
  `DUPLICATE_THRESHOLD`/`SLOW_TEST_SECONDS` to flag only the clearest wins (fewer generated
  tests = fewer LLM calls).

---

## 3. Risk areas

`risk_areas` is a run-time input (CLI `--risk-areas a,b,c`; API `risk_areas: [...]`). Each
entry is matched (case-insensitive substring) against test ids via `is_protected` in
`src/hitl/interrupts.py`. A test is also protected if the long-term memory store marks it so.

**"Protected" means:**
- The test is **pinned** — never placed in the default removal recommendation and never
  removed even if submitted for removal.
- It is **always escalated/shown** at the HITL checkpoint as pinned, so a human sees it but
  can't accidentally drop it.

Use this for critical-path suites (payments, auth, security) you never want trimmed,
regardless of redundancy/flakiness signals.

---

## 4. Data inputs — what's per-run vs fixed

| Input | How it's set | Notes |
|-------|--------------|-------|
| Test suite | `suite_path` (request) / `--suite` (CLI) | Fully configurable; any pytest folder. Defaults to `sample_data/sample_suite`. |
| CI history | **fixed file** `sample_data/mock_ci_history.json` | Path is hard-coded in `src/tools/ci_history.py` — the request can't choose it. Replace the file's contents to use real data. |
| Acceptance criteria | **fixed file** `sample_data/sample_criteria.json` | Path is hard-coded in `src/tools/test_management.py`. Replace the file's contents to use real criteria. |

So pointing `suite_path` at a real repo analyses those tests but still scores them against the
sample CI history/criteria. See [../sample_data/README.md](../sample_data/README.md) §4.

## 5. Corporate TLS / proxies

`src/config.py` injects `truststore` at import so HTTPS uses the **OS certificate store** —
needed behind TLS-inspecting corporate proxies, or the Gemini call fails
`CERTIFICATE_VERIFY_FAILED`. Ensure `truststore` is installed in the same venv that runs the
app. No env var needed; it's automatic.

Note: changing **any** value in `.env` (key or model) requires a **process restart** to take
effect — `uvicorn --reload` watches `.py` files, not `.env`, and the key/client are read once
at startup.

## 6. Persistence — `CHECKPOINT_DB` (for real automation)

LangGraph stores a paused run (waiting at a HITL checkpoint) in a *checkpointer*. By default
that's an in-memory `MemorySaver`, so **paused runs are lost when the process restarts** — fine
for the CLI and the demo.

| Variable | Default | Effect |
|----------|---------|--------|
| `CHECKPOINT_DB` | _(unset)_ | Path to a SQLite file, e.g. `CHECKPOINT_DB=runs.sqlite`. When set, `make_checkpointer()` ([src/graph.py](../src/graph.py)) uses a **persistent `SqliteSaver`** so paused/resumable runs survive restarts. Requires `pip install langgraph-checkpoint-sqlite`; if the package is missing it logs a warning and falls back to in-memory. |

Wire this up before exposing the API/webhook to real (always-on) automation. No code change is
needed — set the env var and restart. The HTTP contract and outputs are unchanged.

---

> ⚠️ **Warning — re-run the golden eval set after tuning.**
> Changing any threshold changes what the agent flags. After editing `src/config.py` (or the
> env overrides), re-run the golden eval set to confirm the known planted findings still fire:
> ```powershell
> python sample_data/generate_sample_data.py    # if you changed the fixture
> pytest tests/test_graph_e2e.py                 # asserts against expected_findings.json
> ```
> If the planted duplicate, flaky, slow, or gap finding no longer appears, your thresholds
> have drifted too far — reconcile against [../sample_data/expected_findings.json](../sample_data/expected_findings.json).
