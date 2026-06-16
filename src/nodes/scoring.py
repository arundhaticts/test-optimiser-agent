"""
Node 5 — Health Scoring.

MUST CONTAIN:
- scoring_node(state) -> dict.
- Call the REASONING model with prompts/scoring_prompt to score the suite across
  the quality dimensions (coverage, redundancy, flakiness, speed, determinism,
  maintainability). Parse the response into structured JSON.
- Each dimension: score + reason + recommended action (independently toggleable).
- Write 'scorecard'. Dimensions lacking data -> 'insufficient evidence', never faked.
"""
