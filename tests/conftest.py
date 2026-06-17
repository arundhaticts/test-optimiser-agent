"""Test isolation: point the long-term memory store at a fresh temp dir per test so
runs don't pollute each other (or the real .agent_memory) via the Phase 5 feedback loop.
"""

import pytest

from src.memory import store as memory


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "_MEM_DIR", tmp_path / ".agent_memory")
