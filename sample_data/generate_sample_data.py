"""
Synthetic sample-data generator for the Test Optimiser agent.

Produces a self-consistent fixture (a 12-test pytest suite + mock CI history +
acceptance criteria + a golden answer key) for DEVELOPING/DEMOING the agent. Nothing
here is training data — it is fully synthetic and deterministic (fixed seed).

Single source of truth: the planted facts (which tests are the near-duplicate pair,
which test is flaky, which is slow, which criterion is the coverage gap) are declared
as constants below, and BOTH the data files and expected_findings.json are built from
them — so the golden set can never drift from the generated data.

Run:  python sample_data/generate_sample_data.py
"""

import json
import random
from pathlib import Path

# --------------------------------------------------------------------------- config
SEED = 7                       # deterministic: re-running produces identical files
RUNS = 50                      # CI runs recorded per test

# ---- PLANTED FACTS (the single source of truth) ----
DUPLICATE_PAIR = ("test_login_success", "test_login_valid_credentials")
DUPLICATE_REASON = ("Both assert a successful login with valid credentials — "
                    "semantically equivalent, different naming/wording.")

FLAKY_TEST = "test_search_returns_results"
FLAKY_FAILS = 18               # 18/50 = 0.36 fail rate (well over a ~10% threshold)

SLOW_TEST = "test_payment_gateway_charges_card"
SLOW_SECONDS = 42.0            # >> the ~0.2-0.9s of every other test

GAP_CRITERION = {"id": "AC-5", "text": "Password reset email is sent within 60s"}

# ---- The 12 tests (name, docstring, body). Bodies are runnable, self-contained
#      stubs asserting simple mocked logic — no external dependencies. Deliberately
#      NO password-reset test exists, so GAP_CRITERION (AC-5) is a true coverage gap. ----
TESTS = [
    ("test_login_success",
     "AC-1: logging in with valid credentials succeeds and authenticates the user.",
     ['users = {"alice": "s3cret"}',
      'def login(username, password):',
      '    return users.get(username) == password',
      'assert login("alice", "s3cret") is True',
      'assert login("alice", "wrong") is False']),

    # Deliberate near-duplicate of test_login_success: a different name but the SAME
    # behaviour and (near-)identical docstring, so the offline similarity clusters them.
    ("test_login_valid_credentials",
     "AC-1: logging in with valid credentials succeeds and authenticates the user "
     "(near-duplicate of test_login_success).",
     ['accounts = {"alice": "s3cret"}',
      'def authenticate(user, pwd):',
      '    return accounts.get(user) == pwd',
      'assert authenticate("alice", "s3cret") is True']),

    ("test_logout",
     "AC-2: logging out ends the active session.",
     ['session = {"alice": True}',
      'def logout(user):',
      '    session[user] = False',
      '    return session[user]',
      'assert logout("alice") is False']),

    ("test_add_to_cart",
     "Adding items increases the cart item count.",
     ['cart = []',
      'def add_to_cart(item):',
      '    cart.append(item)',
      '    return len(cart)',
      'assert add_to_cart("sku-1") == 1',
      'assert add_to_cart("sku-2") == 2']),

    ("test_cart_total_includes_tax",
     "AC-3: the cart total includes tax.",
     ['def cart_total(subtotal, tax_rate=0.1):',
      '    return round(subtotal * (1 + tax_rate), 2)',
      'assert cart_total(100.0) == 110.0']),

    ("test_checkout_creates_order",
     "AC-4: checking out a non-empty cart creates an order.",
     ['orders = []',
      'def checkout(cart):',
      '    if not cart:',
      '        raise ValueError("empty cart")',
      '    order_id = len(orders) + 1',
      '    orders.append({"id": order_id, "items": list(cart)})',
      '    return order_id',
      'assert checkout(["sku-1"]) == 1',
      'assert len(orders) == 1']),

    ("test_payment_gateway_charges_card",
     "The payment gateway charges the card and returns a confirmation "
     "(slow integration in CI history).",
     ['def charge(card_number, amount):',
      '    return {"card": card_number[-4:], "amount": amount, "status": "charged"}',
      'result = charge("4111111111111234", 110.0)',
      'assert result["status"] == "charged"',
      'assert result["card"] == "1234"']),

    ("test_search_returns_results",
     "Searching the catalogue returns the matching products "
     "(flaky in CI history).",
     ['catalogue = ["red shoes", "blue shoes", "red hat"]',
      'def search(query):',
      '    return [p for p in catalogue if query in p]',
      'results = search("red")',
      'assert "red shoes" in results',
      'assert len(results) == 2']),

    ("test_remove_from_cart",
     "Removing an item drops it from the cart.",
     ['cart = ["sku-1", "sku-2"]',
      'def remove(item):',
      '    cart.remove(item)',
      '    return cart',
      'assert remove("sku-1") == ["sku-2"]']),

    ("test_apply_discount_code",
     "A valid discount code reduces the total; an unknown code does not.",
     ['def apply_discount(total, code):',
      '    codes = {"SAVE10": 0.10}',
      '    return round(total * (1 - codes.get(code, 0.0)), 2)',
      'assert apply_discount(100.0, "SAVE10") == 90.0',
      'assert apply_discount(100.0, "BOGUS") == 100.0']),

    ("test_product_listing_pagination",
     "Product listing paginates results into fixed-size pages.",
     ['products = list(range(1, 26))',
      'def paginate(items, page, size=10):',
      '    start = (page - 1) * size',
      '    return items[start:start + size]',
      'assert paginate(products, 1) == list(range(1, 11))',
      'assert len(paginate(products, 3)) == 5']),

    ("test_update_account_email",
     "Updating the account email validates and stores the new address.",
     ['account = {"email": "old@example.com"}',
      'def update_email(new_email):',
      '    if "@" not in new_email:',
      '        raise ValueError("invalid email")',
      '    account["email"] = new_email',
      '    return account["email"]',
      'assert update_email("new@example.com") == "new@example.com"']),
]

# ---- Acceptance criteria: AC-1..AC-4 map to existing tests; AC-5 is the planted gap ----
CRITERIA = [
    {"id": "AC-1", "text": "User can log in with valid credentials"},
    {"id": "AC-2", "text": "User can log out of an active session"},
    {"id": "AC-3", "text": "Cart total includes tax"},
    {"id": "AC-4", "text": "Checkout creates an order"},
    GAP_CRITERION,  # AC-5 — no matching test -> coverage gap
]

# --------------------------------------------------------------------------- paths
BASE = Path(__file__).resolve().parent
SUITE_DIR = BASE / "sample_suite"


# --------------------------------------------------------------------------- writers
def write_suite() -> None:
    lines = [
        "# AUTO-GENERATED by sample_data/generate_sample_data.py — do not edit by hand.",
        "# A synthetic 12-test pytest suite for an e-commerce/auth app. Each test is a",
        "# runnable, self-contained stub asserting simple mocked logic (no external deps).",
        "# Planted: a near-duplicate login pair; flakiness/slowness live in CI history;",
        "# acceptance criterion AC-5 (password reset) has no test here -> coverage gap.",
        "",
    ]
    for name, doc, body in TESTS:
        lines.append(f"def {name}():")
        lines.append(f'    """{doc}"""')
        lines.extend(f"    {stmt}" for stmt in body)
        lines.append("")
    SUITE_DIR.mkdir(parents=True, exist_ok=True)
    (SUITE_DIR / "test_sample.py").write_text("\n".join(lines), encoding="utf-8")


def write_ci_history() -> None:
    rng = random.Random(SEED)
    history = {
        "_comment": (
            f"Mock pass/fail history + run times so flakiness/slow detection works "
            f"without a real CI. Planted flaky test: '{FLAKY_TEST}' "
            f"({FLAKY_FAILS}/{RUNS} fails). Planted slow test: '{SLOW_TEST}' "
            f"({SLOW_SECONDS}s avg). All others are stable (<=1 fail) and fast (<1s)."
        )
    }
    for name, _doc, _body in TESTS:
        if name == FLAKY_TEST:
            entry = {"runs": RUNS, "fails": FLAKY_FAILS,
                     "avg_seconds": round(rng.uniform(0.3, 0.8), 2)}
        elif name == SLOW_TEST:
            entry = {"runs": RUNS, "fails": 0, "avg_seconds": SLOW_SECONDS}
        else:
            entry = {"runs": RUNS, "fails": rng.randint(0, 1),
                     "avg_seconds": round(rng.uniform(0.2, 0.9), 2)}
        history[name] = entry
    (BASE / "mock_ci_history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8")


def write_criteria() -> None:
    data = {
        "_comment": (
            f"Acceptance criteria to match tests against. AC-1..AC-4 map to existing "
            f"tests; the planted coverage GAP is '{GAP_CRITERION['id']}' "
            f"(\"{GAP_CRITERION['text']}\") — no test covers it."
        ),
        "criteria": CRITERIA,
    }
    (BASE / "sample_criteria.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8")


def write_golden() -> None:
    """Golden answer key — derived from the SAME constants, so it cannot drift."""
    golden = {
        "_comment": ("GOLDEN eval set (NOT an input). Derived from the generator's "
                     "planted constants; assert the agent's findings against this."),
        "duplicates": [
            {"tests": list(DUPLICATE_PAIR), "reason": DUPLICATE_REASON}
        ],
        "flaky": [
            {"test": FLAKY_TEST, "fail_rate": round(FLAKY_FAILS / RUNS, 2)}
        ],
        "slow": [
            {"test": SLOW_TEST, "avg_seconds": SLOW_SECONDS}
        ],
        "coverage_gaps": [
            {"criterion_id": GAP_CRITERION["id"], "text": GAP_CRITERION["text"]}
        ],
    }
    (BASE / "expected_findings.json").write_text(
        json.dumps(golden, indent=2), encoding="utf-8")


def main() -> None:
    write_suite()
    write_ci_history()
    write_criteria()
    write_golden()

    print(f"Generated {len(TESTS)} tests into {SUITE_DIR / 'test_sample.py'}")
    print(f"  near-duplicate pair : {DUPLICATE_PAIR[0]}  <->  {DUPLICATE_PAIR[1]}")
    print(f"  flaky test          : {FLAKY_TEST}  ({FLAKY_FAILS}/{RUNS} = "
          f"{round(FLAKY_FAILS / RUNS, 2)})")
    print(f"  slow test           : {SLOW_TEST}  ({SLOW_SECONDS}s avg)")
    print(f"  coverage gap        : {GAP_CRITERION['id']}  \"{GAP_CRITERION['text']}\"")
    print("Files: sample_suite/test_sample.py, mock_ci_history.json, "
          "sample_criteria.json, expected_findings.json")


if __name__ == "__main__":
    main()
