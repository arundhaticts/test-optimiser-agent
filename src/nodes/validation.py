"""
Node 8 — Static Validation (sandbox)  +  bounded-loop routing.

MUST CONTAIN:
- validation_node(state) -> dict: statically validate generated tests in the
  sandbox (tools/sandbox) — syntax + imports only, NEVER against production.
  Set 'validation_passed' / 'needs_regen'.
- route_after_validation(state) -> str: the BOUNDED LOOP (Blocker #1).
  * valid              -> 'approve_tests' (HITL 3)
  * invalid, retries<3 -> 'gap_gen'
  * retries exhausted  -> 'drop_failing' (drop + flag, continue run)
Guarantees the loop can never spin forever.
"""
