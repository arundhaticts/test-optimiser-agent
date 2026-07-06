"""
External integrations + the retry/degrade wrapper (the tools/ integration layer).

Architecture position:
    The integration layer of the agent. Every external call the graph makes (file
    reads, the LLM SDK, subprocess sandboxing, the in-memory vector store, the mocked
    CI/test-management datastores) lives in this package, and every one of those calls
    is funnelled through ``tool_wrapper.call_tool`` (Blocker #3) so a single failed
    dependency degrades gracefully instead of crashing the graph.

Called by:
    - ``tool_wrapper``  <- every I/O node + ``src/llm.py`` (the universal wrapper)
    - ``repo_reader``   <- intake_node (read the suite)
    - ``test_parser``   <- repo_reader (AST parse)
    - ``test_management`` <- coverage_node / retrieval_node (acceptance criteria)
    - ``ci_history``    <- redundancy_node (flaky/slow evidence)
    - ``vector_store``  <- retrieval_node (RAG upsert/query)
    - ``sandbox``       <- validation_node (generated-test syntax check)
    - ``coverage_parser`` (documented stub; not wired in the prototype)

Data in:  the fixed sample fixtures read by the sub-modules
          (``sample_data/sample_suite/*.py``, ``sample_data/sample_criteria.json``,
          ``sample_data/mock_ci_history.json``) plus test code / query text at call time.
Data out: internal test dicts, criteria lists, CI stats, vector hits, and the uniform
          ``{ok, data|error, fatal}`` envelope from ``call_tool``.
"""
