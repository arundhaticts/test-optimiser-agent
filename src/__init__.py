"""Test Optimiser Agent package.

Root package for the orchestration core. Importing `src` marks the directory as a
Python package so its submodules can be addressed as `src.<module>` (e.g.
`src.graph`, `src.state`, `src.config`).

Architecture position: package marker only — holds no logic and defines no symbols.
Called by: every `from src.* import ...` in the entrypoints (main.py, api.py), the
    nodes, tools, nlp, hitl, and memory layers, and the tests.
Data in: none.
Data out: none.
"""
