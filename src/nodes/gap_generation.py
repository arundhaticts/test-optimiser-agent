"""
Node 7 — Gap Test Generation.

MUST CONTAIN:
- gap_generation_node(state) -> dict.
- Call the REASONING model with prompts/gap_generation_prompt to draft tests for the
  highest-risk gaps, matching existing style/conventions (read via tools/repo_reader).
- Each generated test linked to the criterion/path it addresses.
- INCREMENT gen_retry_count here (used by the bounded validation loop).
- Write 'generated_tests'.
"""
