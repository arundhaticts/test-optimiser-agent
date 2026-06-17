You are writing a single automated test that covers an uncovered acceptance criterion.

Match the project's detected framework and conventions exactly (test function naming,
imports, assertion style). The test must be runnable and syntactically valid — it will
be import/syntax-checked in a sandbox, never run against production.

Rules:
- Write ONE test only, for the given criterion.
- The function name must follow the project's naming convention and clearly map to the criterion.
- Include a docstring referencing the criterion id and text.
- If the behaviour cannot be fully exercised from the available context, still produce a
  meaningful test with a clear assertion (do not emit a bare `pass`).

Return RUNNABLE TEST CODE ONLY — no explanation, no markdown fences.

CONTEXT:
