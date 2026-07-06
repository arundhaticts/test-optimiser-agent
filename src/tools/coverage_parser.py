"""
Coverage-report parser (documented stub — not implemented in the prototype).

Planned responsibility: turn a coverage report on disk into per-path coverage data,
with a static call-graph fallback estimator for when no report exists.

Architecture position:
    Integration layer (tools/). When implemented it would be reached only via
    ``tool_wrapper.call_tool`` (Blocker #3), like every other external read. In the
    prototype, coverage is instead projected deterministically by
    ``src/nodes/_coverage_model.coverage_for`` from the parsed suite + similarity links,
    so this module is intentionally left as a documented placeholder and is not wired in.

Called by:  nothing yet (documented stub).
Data in:   (planned) a coverage report path.
Data out:  (planned) per-path coverage data.

MUST CONTAIN (when implemented):
- parse_coverage(path) -> per-path coverage data.
- A static call-graph fallback estimator for when no report exists (degrade path).
"""
