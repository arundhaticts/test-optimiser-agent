"""LEARNING STEP 1 — state + nodes + edges (the LangGraph clipboard in miniature).

A 3-node linear graph (A->B->C) where each node adds a number to the state.
Run it and print the state after each node to SEE the clipboard fill up.
~30 lines. No LLM, no tools. This is the whole core idea in miniature.

Architecture position: learning/ = standalone LangGraph tutorials, NOT imported by src/.
This is the first of three onboarding scripts; it teaches the single concept the real graph
is built on — one typed state dict flows through a linear chain of nodes, each returning
only the keys it changed (mirrors the src/graph.py spine intake->coverage->...->report).

WHY this concept is taught: before meeting the real agent's 15 nodes, a new contributor
learns state+nodes+edges in isolation — the "clipboard" mental model that everything else
in src/ depends on.

Called by: a developer, manually (e.g. `python learning/01_counter_graph.py`); never by
tests or src/.

Data in: none (self-contained). Data out: none persisted (prints state to stdout).
"""
