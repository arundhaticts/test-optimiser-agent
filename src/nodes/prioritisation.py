"""
Node 6 — Risk-based Prioritisation  +  the Coverage-Floor Gate.

MUST CONTAIN:
- prioritisation_node(state) -> dict: re-tier the surviving suite
  (smoke -> regression -> full) weighted by risk, value, and optimization_goal.
  Write 'prioritised_plan'.
- coverage_floor_gate(state) -> str: the ENFORCED gate (Blocker #2).
  Recompute projected_coverage after approved_removals; if below coverage_target,
  return 'revise' (pare back least-valuable removals, re-check); else proceed.
  Risk-area tests are pinned and never removable here.
This is a real conditional node, not prose — it must be able to block a change set.
"""
