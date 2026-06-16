"""
The 3 human-in-the-loop checkpoints.

MUST CONTAIN:
- Payload builders: what the human sees at each checkpoint
  1) removal/quarantine candidates + evidence  -> writes approved_removals
  2) priority ranking & tiers                  -> writes approved_priority
  3) generated tests                           -> writes approved_generated_tests
- The interrupt() calls (or helpers the nodes use).
- run_mode handling stub: interactive = block & wait; automated (webhook/API) =
  checkpoint, notify async, resume on reply (item 5, for phase 2).
- Quarantine vs removal note: quarantine is reversible; removal is always gated.
"""
