# A tiny toy pytest suite to develop against (10-15 tests ideal).
# Include some deliberate duplicates and one obviously slow test so the
# redundancy/flakiness nodes have something real to find.
def test_login_success(): ...
def test_login_success_duplicate(): ...   # near-duplicate on purpose
def test_checkout_total(): ...            # flaky in mock_ci_history (18/50 fails)
def test_payment_gateway(): ...           # slow in mock_ci_history (42s avg)
