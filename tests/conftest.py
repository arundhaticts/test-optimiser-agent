"""Shared pytest fixtures — memory-store isolation for the whole test suite.

Point the long-term memory store at a fresh temp dir per test so runs don't pollute each
other (or the real .agent_memory) via the Phase 5 feedback loop.

Architecture position: tests/ = the safety net. conftest.py is the memory-isolation
fixture shared by every test module (test_state, test_coverage_gate, test_validation_loop,
test_graph_e2e). It guarantees each test sees a clean long-term store.

Called by: pytest (auto-discovered; the fixture is autouse, so it applies to every test
without being requested explicitly).

Data in: none (constructs a fresh path under pytest's tmp_path).
Data out: none persisted — the temp .agent_memory dir is discarded after each test.
"""

import pytest

from src.memory import store as memory


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Redirect the memory store to a per-test temp dir so runs stay isolated.

    Purpose: prevent the report node's save_decision/record_flaky writes (the Phase 5
    feedback loop) from leaking between tests or touching the real .agent_memory dir —
    each test gets a clean slate, so prior-decision/protected/flaky state is deterministic.
    Inputs: tmp_path (pytest per-test temp dir), monkeypatch (attribute patcher).
    Outputs: None (yields nothing; used purely for its side effect).
    Side effects: temp-dir memory redirect — monkeypatches src.memory.store._MEM_DIR to
        tmp_path/.agent_memory; monkeypatch auto-reverts it after the test.
    Called by: pytest (autouse — applied to every test automatically).
    Calls: monkeypatch.setattr.
    """
    # WHY: the memory store's module-level _MEM_DIR decides where per-project JSON files
    # land; repointing it at a throwaway temp dir isolates each test's durable writes.
    monkeypatch.setattr(memory, "_MEM_DIR", tmp_path / ".agent_memory")
