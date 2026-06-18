"""
Synthetic sample-data generator for the Test Optimiser agent.

Produces a self-consistent fixture for DEVELOPING/DEMOING the agent — a realistic
e-commerce/auth pytest suite split across several files, plus mock CI history,
acceptance criteria, and a golden answer key. Nothing here is training data; it is
fully synthetic and deterministic (fixed seed), so re-running yields identical files.

Single source of truth: the planted facts (which tests are near-duplicates, which are
flaky/slow, which criteria are coverage gaps) are declared as constants below, and
BOTH the data files and expected_findings.json are built from them — so the golden set
can never drift from the generated data.

Run:  python sample_data/generate_sample_data.py
"""

import json
import random
from pathlib import Path

# --------------------------------------------------------------------------- config
SEED = 7          # deterministic: re-running produces identical files
RUNS = 50         # CI runs recorded per test

# ---- PLANTED FACTS (the single source of truth) ----
# Two near-duplicate clusters. Partners share a (near-)identical docstring so the
# offline lexical similarity clusters them above DUPLICATE_THRESHOLD.
DUPLICATE_PAIRS = [
    ("test_login_success", "test_login_valid_credentials"),
    ("test_add_item_to_cart", "test_cart_add_item"),
]
# Flaky tests: (test_id, fails out of RUNS). 18/50 = 0.36, 16/50 = 0.32 — both well over
# the ~10% flaky threshold.
FLAKY = [("test_search_returns_results", 18), ("test_checkout_payment_retry", 16)]
# Slow tests: (test_id, avg_seconds) — far above every other test's sub-second time.
SLOW = [("test_payment_gateway_charges_card", 42.0), ("test_full_catalog_export", 19.0)]
# Risk area: any test whose id contains this is pinned (never removable). The demo/e2e
# passes risk_areas=["payment"], which pins test_payment_gateway_charges_card.
RISK_HINT = "payment"

# Acceptance criteria. AC-1..AC-5 map to existing tests; AC-6 and AC-7 are the planted
# coverage GAPS — no test covers them.
CRITERIA = [
    {"id": "AC-1", "text": "User can log in with valid credentials"},
    {"id": "AC-2", "text": "User can log out of an active session"},
    {"id": "AC-3", "text": "Cart total includes tax"},
    {"id": "AC-4", "text": "Checkout creates an order"},
    {"id": "AC-5", "text": "Search returns matching products"},
    {"id": "AC-6", "text": "Password reset email is sent within 60s"},
    {"id": "AC-7", "text": "Inventory stock levels update after each purchase"},
]
GAP_IDS = ["AC-6", "AC-7"]

# Shared docstrings for the duplicate partners (identical → guaranteed to cluster).
_D_LOGIN = "AC-1: logging in with valid credentials succeeds and authenticates the user."
_D_CART_ADD = "Adding an item to the cart increases the cart item count by one."

# ---- The suite, grouped into files by domain. Each test is a runnable, self-contained
#      stub asserting simple mocked logic (no external deps). Test function names are
#      unique across ALL files (the agent keys on the function name). ----
# FILES: filename -> (one-line file purpose, [ (name, docstring, body_lines) ])
FILES = {
    "test_auth.py": (
        "Authentication & session tests (login, logout, session, sign-up).",
        [
            ("test_login_success", _D_LOGIN,
             ['users = {"alice": "s3cret"}',
              'def login(u, p):',
              '    return users.get(u) == p',
              'assert login("alice", "s3cret") is True',
              'assert login("alice", "wrong") is False']),
            ("test_login_valid_credentials", f"{_D_LOGIN} (near-duplicate of test_login_success).",
             ['accounts = {"alice": "s3cret"}',
              'def authenticate(user, pwd):',
              '    return accounts.get(user) == pwd',
              'assert authenticate("alice", "s3cret") is True']),
            ("test_logout", "AC-2: logging out ends the active session.",
             ['session = {"alice": True}',
              'def logout(user):',
              '    session[user] = False',
              '    return session[user]',
              'assert logout("alice") is False']),
            ("test_session_expiry", "An idle session expires after the timeout elapses.",
             ['def is_expired(idle_seconds, timeout=900):',
              '    return idle_seconds >= timeout',
              'assert is_expired(1000) is True',
              'assert is_expired(10) is False']),
            ("test_weak_signup_rejected", "Weak credentials are rejected at sign-up.",
             ['def strong_enough(secret):',
              '    return len(secret) >= 8',
              'assert strong_enough("longenough") is True',
              'assert strong_enough("abc") is False']),
        ],
    ),
    "test_cart.py": (
        "Shopping-cart tests (add, remove, totals, discounts, persistence).",
        [
            ("test_add_item_to_cart", _D_CART_ADD,
             ['cart = []',
              'def add(item):',
              '    cart.append(item)',
              '    return len(cart)',
              'assert add("sku-1") == 1']),
            ("test_cart_add_item", f"{_D_CART_ADD} (near-duplicate of test_add_item_to_cart).",
             ['items = []',
              'def add_to_cart(sku):',
              '    items.append(sku)',
              '    return len(items)',
              'assert add_to_cart("sku-9") == 1']),
            ("test_remove_item_from_cart", "Removing an item drops it from the cart.",
             ['cart = ["sku-1", "sku-2"]',
              'def remove(item):',
              '    cart.remove(item)',
              '    return cart',
              'assert remove("sku-1") == ["sku-2"]']),
            ("test_cart_total_includes_tax", "AC-3: the cart total includes tax.",
             ['def cart_total(subtotal, tax_rate=0.1):',
              '    return round(subtotal * (1 + tax_rate), 2)',
              'assert cart_total(100.0) == 110.0']),
            ("test_apply_discount_code", "A valid discount code reduces the cart total.",
             ['def apply(total, code):',
              '    return round(total * (1 - {"SAVE10": 0.10}.get(code, 0.0)), 2)',
              'assert apply(100.0, "SAVE10") == 90.0',
              'assert apply(100.0, "NOPE") == 100.0']),
            ("test_cart_persists_between_visits", "The cart is restored when the user returns.",
             ['store = {"alice": ["sku-1"]}',
              'def restore(user):',
              '    return store.get(user, [])',
              'assert restore("alice") == ["sku-1"]']),
        ],
    ),
    "test_checkout.py": (
        "Checkout & payment tests (orders, payment, retries, confirmation).",
        [
            ("test_checkout_creates_order", "AC-4: checking out a non-empty cart creates an order.",
             ['orders = []',
              'def checkout(cart):',
              '    if not cart:',
              '        raise ValueError("empty cart")',
              '    orders.append(cart)',
              '    return len(orders)',
              'assert checkout(["sku-1"]) == 1']),
            ("test_payment_gateway_charges_card",
             "The payment gateway charges the card and returns a confirmation "
             "(slow integration; risk-area: payment).",
             ['def charge(card, amount):',
              '    return {"card": card[-4:], "amount": amount, "status": "charged"}',
              'r = charge("4111111111111234", 110.0)',
              'assert r["status"] == "charged" and r["card"] == "1234"']),
            ("test_checkout_payment_retry", "A failed payment is retried and eventually succeeds.",
             ['def pay(attempts):',
              '    return "ok" if attempts >= 2 else "retry"',
              'assert pay(2) == "ok"',
              'assert pay(1) == "retry"']),
            ("test_order_confirmation_email", "An order confirmation message is queued after checkout.",
             ['queue = []',
              'def confirm(order_id):',
              '    queue.append(order_id)',
              '    return len(queue)',
              'assert confirm(1) == 1']),
            ("test_order_blocked_when_basket_empty", "An order cannot be placed when the basket is empty.",
             ['def place_order(basket):',
              '    if not basket:',
              '        return "blocked"',
              '    return "ok"',
              'assert place_order([]) == "blocked"']),
        ],
    ),
    "test_search.py": (
        "Catalogue search tests (matching, empty results, export, pagination).",
        [
            ("test_search_returns_results", "AC-5: searching the catalogue returns the matching products "
             "(flaky in CI history).",
             ['catalogue = ["red shoes", "blue shoes", "red hat"]',
              'def search(q):',
              '    return [p for p in catalogue if q in p]',
              'assert "red shoes" in search("red")']),
            ("test_search_no_results", "Searching for an unknown term returns no products.",
             ['catalogue = ["red shoes"]',
              'def search(q):',
              '    return [p for p in catalogue if q in p]',
              'assert search("laptop") == []']),
            ("test_full_catalog_export", "Exporting the full product catalogue returns every product "
             "(slow in CI history).",
             ['catalogue = list(range(1, 6))',
              'def export_all():',
              '    return list(catalogue)',
              'assert export_all() == [1, 2, 3, 4, 5]']),
            ("test_search_pagination", "Search results are paginated into fixed-size pages.",
             ['def page(items, n, size=10):',
              '    return items[(n - 1) * size:(n - 1) * size + size]',
              'assert page(list(range(25)), 1) == list(range(10))']),
        ],
    ),
    "test_account.py": (
        "Account-management tests (profile, email, deletion).",
        [
            ("test_update_account_email", "Updating the account email validates and stores the new address.",
             ['acct = {"email": "old@example.com"}',
              'def update(email):',
              '    if "@" not in email:',
              '        raise ValueError("invalid")',
              '    acct["email"] = email',
              '    return acct["email"]',
              'assert update("new@example.com") == "new@example.com"']),
            ("test_update_profile_name", "Updating the profile stores the new display name.",
             ['profile = {"name": "Alice"}',
              'def rename(name):',
              '    profile["name"] = name',
              '    return profile["name"]',
              'assert rename("Alicia") == "Alicia"']),
            ("test_delete_account", "Deleting an account removes the user record.",
             ['accounts = {"alice": {}}',
              'def delete(user):',
              '    accounts.pop(user, None)',
              '    return user not in accounts',
              'assert delete("alice") is True']),
        ],
    ),
}

# --------------------------------------------------------------------------- derived
BASE = Path(__file__).resolve().parent
SUITE_DIR = BASE / "sample_suite"

_FLAKY_MAP = dict(FLAKY)
_SLOW_MAP = dict(SLOW)


def _all_tests():
    """Flat [(name, docstring, body)] across all files, preserving order."""
    for _fname, (_desc, tests) in FILES.items():
        for t in tests:
            yield t


# --------------------------------------------------------------------------- writers
def write_suite() -> None:
    SUITE_DIR.mkdir(parents=True, exist_ok=True)
    # Clear stale generated files so old test names can't collide with the new set.
    for old in SUITE_DIR.glob("test_*.py"):
        old.unlink()

    for fname, (desc, tests) in FILES.items():
        lines = [
            f"# AUTO-GENERATED by sample_data/generate_sample_data.py — do not edit by hand.",
            f"# {desc}",
            f"# Each test is a runnable, self-contained pytest stub (no external deps).",
            "",
        ]
        for name, doc, body in tests:
            lines.append(f"def {name}():")
            lines.append(f'    """{doc}"""')
            lines.extend(f"    {stmt}" for stmt in body)
            lines.append("")
        (SUITE_DIR / fname).write_text("\n".join(lines), encoding="utf-8")


def write_ci_history() -> None:
    rng = random.Random(SEED)
    flaky_desc = ", ".join(f"{n} ({f}/{RUNS})" for n, f in FLAKY)
    slow_desc = ", ".join(f"{n} ({s}s)" for n, s in SLOW)
    history = {
        "_comment": (
            "Mock pass/fail history + average run time per test, so flakiness/slow "
            "detection works without a real CI. One entry per test in sample_suite/. "
            f"Planted flaky tests: {flaky_desc}. Planted slow tests: {slow_desc}. "
            "Every other test is stable (<=1 fail) and fast (<1s)."
        )
    }
    for name, _doc, _body in _all_tests():
        if name in _FLAKY_MAP:
            entry = {"runs": RUNS, "fails": _FLAKY_MAP[name],
                     "avg_seconds": round(rng.uniform(0.3, 0.8), 2)}
        elif name in _SLOW_MAP:
            entry = {"runs": RUNS, "fails": 0, "avg_seconds": _SLOW_MAP[name]}
        else:
            entry = {"runs": RUNS, "fails": rng.randint(0, 1),
                     "avg_seconds": round(rng.uniform(0.2, 0.9), 2)}
        history[name] = entry
    (BASE / "mock_ci_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")


def write_criteria() -> None:
    gaps_desc = "; ".join(f"{c['id']} (\"{c['text']}\")" for c in CRITERIA if c["id"] in GAP_IDS)
    data = {
        "_comment": (
            "Acceptance criteria the suite is matched against (these would come from a "
            "User Story Analyser / Jira). AC-1..AC-5 map to existing tests; the planted "
            f"coverage GAPS are: {gaps_desc} — no test covers them."
        ),
        "criteria": CRITERIA,
    }
    (BASE / "sample_criteria.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_golden() -> None:
    """Golden answer key — derived from the SAME constants, so it cannot drift."""
    golden = {
        "_comment": ("GOLDEN eval set (NOT an input). Derived from the generator's planted "
                     "constants; the e2e test asserts the agent's findings against this."),
        "duplicates": [
            {"tests": list(pair),
             "reason": "Same behaviour, different name/wording — semantically equivalent."}
            for pair in DUPLICATE_PAIRS
        ],
        "flaky": [{"test": n, "fail_rate": round(f / RUNS, 2)} for n, f in FLAKY],
        "slow": [{"test": n, "avg_seconds": s} for n, s in SLOW],
        "coverage_gaps": [
            {"criterion_id": c["id"], "text": c["text"]} for c in CRITERIA if c["id"] in GAP_IDS
        ],
    }
    (BASE / "expected_findings.json").write_text(json.dumps(golden, indent=2), encoding="utf-8")


def write_readme() -> None:
    total = sum(len(tests) for _d, tests in FILES.values())
    dup_partner: dict[str, str] = {}
    for a, b in DUPLICATE_PAIRS:
        dup_partner[a], dup_partner[b] = b, a
    flaky_map, slow_map = dict(FLAKY), dict(SLOW)

    L = [
        "# sample_data — the Test Optimiser agent's synthetic fixture",
        "",
        "> ⚠️ **Every file in this folder is generated by `generate_sample_data.py`.** Do not",
        "> hand-edit them — your changes will be overwritten the next time the generator runs.",
        "> To change the data, edit the constants at the top of that script and re-run it.",
        "",
        "This document explains, in detail: **what this folder is**, **how it is created**,",
        "**exactly what each file contains**, and **how the running app (backend + React",
        "frontend) actually uses it**. If you read nothing else, read the *Mental model* and",
        "*§4 Runtime flow* sections.",
        "",
        "## Mental model (read this first)",
        "",
        "The Test Optimiser agent looks at an existing automated **test suite** and produces an",
        "optimised plan: which tests are redundant, flaky, slow, and which requirements have no",
        "test (coverage gaps). To do that it needs three kinds of input, and for *demoing and",
        "testing* the agent we fake all three here so the run is fast, offline, and repeatable:",
        "",
        "1. **The test suite itself** — real `.py` test files the agent reads → `sample_suite/`.",
        "2. **CI history** — how often each test has failed and how long it takes, so the agent",
        "   can call a test 'flaky' or 'slow' → `mock_ci_history.json`.",
        "3. **Acceptance criteria** — the requirements the suite is supposed to cover, so the",
        "   agent can spot requirements with **no** matching test → `sample_criteria.json`.",
        "",
        "On top of those three *inputs* there is one extra file, **`expected_findings.json`** —",
        "the **golden answer key**. It is *not* fed to the agent; it records the findings we",
        "deliberately planted, so the automated test can check the agent actually finds them.",
        "",
        "### Glossary",
        "",
        "- **test id** — the Python function name (e.g. `test_login_success`). Unique across all files.",
        "- **finding** — something the agent flags: a duplicate, a flaky test, a slow test, or a gap.",
        "- **coverage gap** — an acceptance criterion (AC-*) that no test covers.",
        "- **tier** — `smoke` / `regression` / `full`; how often a test should run.",
        "- **planted** — a finding we engineered into the data on purpose so a detector has something to catch.",
        "- **golden set** — the expected findings (`expected_findings.json`) used to grade the agent.",
        "",
        "---",
        "",
        "## 1. How this data is created (the generation flow)",
        "",
        "`generate_sample_data.py` is the **single source of truth**. Near the top it declares the",
        "*planted facts* as plain Python constants:",
        "",
        "- `DUPLICATE_PAIRS` — pairs of tests that should be detected as near-duplicates.",
        "- `FLAKY` — `(test_id, fails-out-of-50)` for each test that should look flaky.",
        "- `SLOW` — `(test_id, avg_seconds)` for each test that should look slow.",
        "- `CRITERIA` + `GAP_IDS` — the acceptance criteria, and which of them have no test.",
        "- `FILES` — the whole suite: a filename → list of `(test name, docstring, body)`.",
        "",
        "Running the script turns those constants into five outputs. The arrows show which",
        "constant drives which file:",
        "",
        "```",
        "generate_sample_data.py   (FILES, DUPLICATE_PAIRS, FLAKY, SLOW, CRITERIA, GAP_IDS)",
        "        |   $ python sample_data/generate_sample_data.py",
        "        |",
        "        +--> sample_suite/test_*.py     <- FILES                 (the test code)",
        "        +--> mock_ci_history.json       <- FLAKY + SLOW          (CI stats)",
        "        +--> sample_criteria.json       <- CRITERIA + GAP_IDS    (requirements)",
        "        +--> expected_findings.json     <- ALL of the above      (the answer key)",
        "        +--> README.md                  <- everything            (this file)",
        "```",
        "",
        "Two properties matter:",
        "",
        "- **Single source of truth.** Because the data files *and* the answer key come from the",
        "  same constants, they can never disagree. If you make `test_x` flaky in `FLAKY`, it",
        "  appears in `mock_ci_history.json` *and* in `expected_findings.json` automatically.",
        "- **Deterministic.** A fixed random seed (`SEED`) means re-running produces byte-for-byte",
        "  identical files. The only randomness is the boring filler (stable tests' sub-second",
        "  run times); the planted facts are exact.",
        "",
        "This is why you must never hand-edit the outputs: a hand edit to, say,",
        "`mock_ci_history.json` would make it disagree with `expected_findings.json`, and the",
        "end-to-end test would (correctly) fail. Change the constant instead and regenerate.",
        "",
        "---",
        "",
        "## 2. File-by-file overview",
        "",
        "| File | Role | Who reads it at runtime |",
        "|------|------|-------------------------|",
        "| `generate_sample_data.py` | The generator / single source of truth | nobody — you run it by hand |",
        f"| `sample_suite/` | The **test suite** under analysis ({total} tests in {len(FILES)} files) | the `intake` node |",
    ]
    for fname, (desc, tests) in FILES.items():
        L.append(f"| `sample_suite/{fname}` | {desc} ({len(tests)} tests) | (part of the suite) |")
    L += [
        "| `mock_ci_history.json` | Per-test pass/fail counts + run time | the `redundancy` node |",
        "| `sample_criteria.json` | Acceptance criteria (`AC-*`) | the `coverage` node |",
        "| `expected_findings.json` | **Golden answer key** (NOT an input) | only `tests/test_graph_e2e.py` |",
        "",
        "---",
        "",
        "## 3. Exact content of each file",
        "",
        "### 3.1  `sample_suite/*.py` — the test suite",
        "",
        "These are ordinary pytest files. Rules the agent relies on:",
        "",
        "- One test = one `def test_*()` function. **The function name is the test id**, and it",
        "  must be unique across every file (the agent keys CI history, coverage, and findings on it).",
        "- The agent reads the files with Python's `ast` module — it parses the *source* and the",
        "  *docstring* but **never executes the tests**. The docstring is important: it's the main",
        "  text used to match a test to a criterion and to cluster near-duplicates.",
        "- Each test here is a tiny, self-contained, runnable stub (it mocks its own logic, no",
        "  external imports), so `pytest sample_data/sample_suite` passes on its own.",
        "",
        "A test looks like this:",
        "",
        "```python",
        "def test_login_success():",
        '    """AC-1: logging in with valid credentials succeeds and authenticates the user."""',
        '    users = {"alice": "s3cret"}',
        "    def login(u, p):",
        "        return users.get(u) == p",
        '    assert login("alice", "s3cret") is True',
        "```",
        "",
        f"The {total} tests, file by file (the text in quotes is the real docstring; tags mark what's planted):",
        "",
    ]
    for fname, (desc, tests) in FILES.items():
        L.append(f"#### `{fname}` — {desc}")
        for name, doc, _body in tests:
            tags = []
            if name in dup_partner:
                tags.append(f"near-duplicate of `{dup_partner[name]}`")
            if name in flaky_map:
                tags.append(f"**flaky** ({flaky_map[name]}/{RUNS})")
            if name in slow_map:
                tags.append(f"**slow** ({slow_map[name]}s)")
            if RISK_HINT in name:
                tags.append("**risk-pinned**")
            suffix = f"  _[{'; '.join(tags)}]_" if tags else ""
            L.append(f"- `{name}` — \"{doc}\"{suffix}")
        L.append("")
    L += [
        "### 3.2  `mock_ci_history.json` — the flaky/slow signal",
        "",
        "A JSON object keyed by test id. Each value records how that test behaved across",
        f"`runs` CI runs ({RUNS} here): how many `fails`, and the `avg_seconds` per run. There is",
        "one `_comment` key (ignored by the loader) describing what was planted. Shape:",
        "",
        "```jsonc",
        "{",
        '  "_comment": "... planted flaky/slow tests ...",',
        '  "test_login_success":                { "runs": 50, "fails": 1,  "avg_seconds": 0.8 },   // stable + fast',
        '  "test_search_returns_results":       { "runs": 50, "fails": 18, "avg_seconds": 0.5 },   // FLAKY  (18/50 = 36%)',
        '  "test_payment_gateway_charges_card": { "runs": 50, "fails": 0,  "avg_seconds": 42.0 }   // SLOW   (>= 10s)',
        "  // ...one entry for every test in the suite...",
        "}",
        "```",
        "",
        "How the agent uses it (in the `redundancy` node, via `src/tools/ci_history.py`):",
        "",
        "- **Flaky** when `fails / runs >= FLAKY_FAIL_RATE` (default **0.10**, i.e. 10%).",
        "- **Slow** when `avg_seconds >= SLOW_TEST_SECONDS` (default **10.0**).",
        "- A test with **no entry** isn't guessed about — it degrades to \"needs more data\".",
        "",
        "Every non-planted test here is given a stable record (0–1 fails, a seeded sub-second time)",
        "so it stays comfortably under both thresholds and does *not* get flagged.",
        "",
        "### 3.3  `sample_criteria.json` — the coverage signal",
        "",
        "The acceptance criteria the suite is supposed to satisfy (in a real system these come from",
        "Jira / a User-Story analyser). Shape: a `criteria` list of `{id, text}` plus a `_comment`:",
        "",
        "```jsonc",
        "{",
        '  "_comment": "... which criteria are the planted gaps ...",',
        '  "criteria": [',
    ]
    for c in CRITERIA:
        tag = "   // GAP — no test covers this" if c["id"] in GAP_IDS else ""
        L.append(f'    {{ "id": "{c["id"]}", "text": "{c["text"]}" }},{tag}')
    L += [
        "  ]",
        "}",
        "",
        "How the agent uses it (in the `coverage` node): every criterion is compared to every",
        "test's text (name + docstring) by similarity. A test is linked to a criterion when the",
        "score is `>= CRITERIA_MATCH_THRESHOLD` (default **0.45**). A criterion whose best match",
        "is below `GAP_THRESHOLD` (default **0.45**) is reported as a **coverage gap**. The two",
        "gap criteria above are worded so that no test in the suite matches them.",
        "",
        "### 3.4  `expected_findings.json` — the golden answer key",
        "",
        "The findings we *planted*, in a compact shape. **The agent never reads this file.** Only",
        "`tests/test_graph_e2e.py` loads it, runs the whole agent on the suite, and asserts the",
        "agent's output reproduces every entry here. Shape:",
        "",
        "```json",
        "{",
        '  "duplicates":    [ { "tests": ["test_a", "test_b"], "reason": "..." } ],',
        '  "flaky":         [ { "test": "test_x", "fail_rate": 0.36 } ],',
        '  "slow":          [ { "test": "test_y", "avg_seconds": 42.0 } ],',
        '  "coverage_gaps": [ { "criterion_id": "AC-6", "text": "..." } ]',
        "}",
        "```",
        "",
        "---",
        "",
        "## 4. Runtime flow — what the frontend actually touches",
        "",
        "When you click **Run Analysis** in the React UI, the frontend sends one HTTP request to",
        "the FastAPI backend (`api.py`):",
        "",
        "```",
        "POST /runs",
        "{ suite_path, project_id, optimization_goal, coverage_target, risk_areas, run_mode }",
        "```",
        "",
        "Of those fields, **only `suite_path` chooses any data** — and the form defaults it to",
        "`sample_data/sample_suite`. The backend hands the request to the LangGraph agent, whose",
        "nodes pull in the data files like this:",
        "",
        "```",
        "Frontend (InputPanel)  --POST /runs-->  api.py  -->  LangGraph nodes",
        "                                                       |",
        "  intake     -> repo_reader.read_tests(suite_path)     -> reads sample_suite/*.py      [from your request]",
        "  coverage   -> test_management.get_acceptance_criteria() -> reads sample_criteria.json   [FIXED path]",
        "  redundancy -> ci_history.get_history(test_id)        -> reads mock_ci_history.json    [FIXED path]",
        "```",
        "",
        "**The most important thing to understand:** only the **suite** is chosen by the request.",
        "`mock_ci_history.json` and `sample_criteria.json` are read from **hard-coded paths** baked",
        "into `src/tools/ci_history.py` and `src/tools/test_management.py`. The frontend has no",
        "field for them. So if you point `suite_path` at a *different* test folder, the agent will",
        "analyse those tests but still use **this folder's** CI history and criteria — meaning your",
        "tests will mostly show \"needs more data\" for flakiness and won't match your real",
        "requirements. `expected_findings.json` is never read during a run; it is test-only.",
        "",
        "The results you see in the UI come back in the run's `final_outputs` (scorecard, coverage",
        "& gap map, redundancy & flakiness report, optimised plan). Approving a generated test at",
        "the third checkpoint tags the relevant gap as *addressed by* that draft test in the",
        "Coverage Map — the criterion stays a gap until the test is actually implemented and merged.",
        "",
        "---",
        "",
        "## 5. What's planted (the cheat sheet)",
        "",
        "Each line below is engineered into the data so a specific detector has something to find.",
        "The detector reads the file named in brackets.",
        "",
    ]
    for a, b in DUPLICATE_PAIRS:
        L.append(f"- **Duplicate cluster** [suite docstrings]: `{a}` and `{b}` — same behaviour, "
                 f"near-identical docstrings, so similarity clusters them.")
    for n, f in FLAKY:
        L.append(f"- **Flaky** [mock_ci_history.json]: `{n}` — {f}/{RUNS} fails = {round(f / RUNS, 2)} (over the 10% line).")
    for n, s in SLOW:
        L.append(f"- **Slow** [mock_ci_history.json]: `{n}` — {s}s average (over the 10s line).")
    for c in CRITERIA:
        if c["id"] in GAP_IDS:
            L.append(f"- **Coverage gap** [sample_criteria.json]: `{c['id']}` — \"{c['text']}\" (no test matches it).")
    L += [
        f"- **Risk pin** [request `risk_areas`]: any test whose name contains `{RISK_HINT}` is "
        f"pinned and can never be removed when the run sets `risk_areas=[\"{RISK_HINT}\"]` "
        f"(e.g. `test_payment_gateway_charges_card`).",
        "",
        "---",
        "",
        "## 6. Using your own data instead",
        "",
        "- **Your own tests:** set `suite_path` (UI) or `--suite` (CLI) to any pytest folder, e.g.",
        "  `C:/work/my-app/tests`. That part works today.",
        "- **Your own CI history / criteria:** there is no UI field for these yet. Either (a) replace",
        "  the *contents* of `mock_ci_history.json` and `sample_criteria.json` with your real data,",
        "  keeping the same shapes (test ids must match your test function names); or (b) wire",
        "  `src/tools/ci_history.py` / `src/tools/test_management.py` to your real sources.",
        "",
        "---",
        "",
        "## 7. Regenerate",
        "",
        "```bash",
        "python sample_data/generate_sample_data.py",
        "```",
        "",
        "Edit the constants at the top of the script first if you want to change what's planted —",
        "the suite, the CI history, the criteria, the golden key, and this README are all rewritten",
        "from them, so they stay perfectly in sync.",
        "",
    ]
    (BASE / "README.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    write_suite()
    write_ci_history()
    write_criteria()
    write_golden()
    write_readme()

    total = sum(len(tests) for _d, tests in FILES.values())
    print(f"Generated {total} tests across {len(FILES)} files in {SUITE_DIR}")
    for fname, (_desc, tests) in FILES.items():
        print(f"  {fname:<22} {len(tests)} tests")
    print("Planted:")
    print(f"  duplicate clusters : {len(DUPLICATE_PAIRS)} -> {', '.join(a + ' <-> ' + b for a, b in DUPLICATE_PAIRS)}")
    print(f"  flaky              : {', '.join(n for n, _ in FLAKY)}")
    print(f"  slow               : {', '.join(n for n, _ in SLOW)}")
    print(f"  coverage gaps      : {', '.join(GAP_IDS)}")
    print("Files: sample_suite/*.py, mock_ci_history.json, sample_criteria.json, "
          "expected_findings.json, README.md")


if __name__ == "__main__":
    main()
