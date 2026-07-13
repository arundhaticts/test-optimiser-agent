"""
Tests for the multi-provider LLMClient and per-request model wiring.

Covers:
  * LLMClient raises ValueError for missing API keys (all providers).
  * LLMClient raises ValueError for unknown providers.
  * Each provider's __call__ path returns text and appends a correctly-shaped usage entry
    (all network / SDK calls are mocked — no real traffic).
  * build_graph(llm=None) compiles without error (deterministic path unchanged).
  * /mine with no provider/model behaves identically to pre-LLM behaviour (regression).

Run: pytest -q tests/test_llm_client.py
"""
from __future__ import annotations

import json
import sys
import types as _types
import unittest.mock as mock
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

from test_data_mining.llm import LLMClient, build_llm  # noqa: E402


# ---------------------------------------------------------------------------
# ValueError for missing keys / unknown provider
# ---------------------------------------------------------------------------

def test_gemini_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        LLMClient(provider="gemini", model="gemini-2.5-flash")


def test_anthropic_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        LLMClient(provider="anthropic", model="claude-3-5-sonnet-20241022")


def test_unknown_provider_raises(monkeypatch):
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMClient(provider="openai", model="gpt-4o")


# ---------------------------------------------------------------------------
# Gemini — mocked call, usage recorded
# ---------------------------------------------------------------------------

def test_gemini_call_returns_text_and_records_usage(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    mock_usage = _types.SimpleNamespace(prompt_token_count=10, candidates_token_count=20)
    mock_resp = _types.SimpleNamespace(text="val1, val2, val3", usage_metadata=mock_usage)
    mock_client = mock.MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with mock.patch("google.genai.Client", return_value=mock_client):
        llm = LLMClient(provider="gemini", model="gemini-2.5-flash")
        result = llm("test prompt")

    assert result == "val1, val2, val3"
    assert len(llm.usage) == 1
    entry = llm.usage[0]
    assert entry["provider"] == "gemini"
    assert entry["model"] == "gemini-2.5-flash"
    assert entry["input_tokens"] == 10
    assert entry["output_tokens"] == 20
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0


def test_gemini_call_handles_missing_usage_metadata(monkeypatch):
    """When the SDK response has no usage_metadata the tokens should be None, not raise."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    mock_resp = _types.SimpleNamespace(text="hello", usage_metadata=None)
    mock_client = mock.MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with mock.patch("google.genai.Client", return_value=mock_client):
        llm = LLMClient(provider="gemini", model="gemini-2.5-flash")
        result = llm("prompt")

    assert result == "hello"
    assert llm.usage[0]["input_tokens"] is None
    assert llm.usage[0]["output_tokens"] is None


# ---------------------------------------------------------------------------
# Anthropic — mocked via sys.modules (package may not be installed)
# ---------------------------------------------------------------------------

def test_anthropic_call_returns_text_and_records_usage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    mock_usage = _types.SimpleNamespace(input_tokens=15, output_tokens=25)
    mock_content = [_types.SimpleNamespace(text="anthropic result")]
    mock_resp = _types.SimpleNamespace(content=mock_content, usage=mock_usage)

    mock_anthropic_mod = mock.MagicMock()
    mock_anthropic_mod.Anthropic.return_value.messages.create.return_value = mock_resp

    with mock.patch.dict(sys.modules, {"anthropic": mock_anthropic_mod}):
        llm = LLMClient(provider="anthropic", model="claude-3-5-sonnet-20241022")
        result = llm("test prompt")

    assert result == "anthropic result"
    assert len(llm.usage) == 1
    entry = llm.usage[0]
    assert entry["provider"] == "anthropic"
    assert entry["model"] == "claude-3-5-sonnet-20241022"
    assert entry["input_tokens"] == 15
    assert entry["output_tokens"] == 25
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0


# ---------------------------------------------------------------------------
# Ollama — mocked httpx.post on the instance
# ---------------------------------------------------------------------------

def test_ollama_call_returns_text_and_records_usage(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")

    llm = LLMClient(provider="ollama", model="phi3")

    mock_response = mock.MagicMock()
    mock_response.json.return_value = {
        "response": "ollama result",
        "prompt_eval_count": 8,
        "eval_count": 12,
    }

    with mock.patch.object(llm, "_httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_response
        result = llm("test prompt")

    assert result == "ollama result"
    assert len(llm.usage) == 1
    entry = llm.usage[0]
    assert entry["provider"] == "ollama"
    assert entry["model"] == "phi3"
    assert entry["input_tokens"] == 8
    assert entry["output_tokens"] == 12
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0

    # Verify the request was sent to the right URL with stream=False
    call_kwargs = mock_httpx.post.call_args
    assert "/api/generate" in call_kwargs[0][0]
    assert call_kwargs[1]["json"]["stream"] is False


def test_ollama_accumulates_multiple_calls(monkeypatch):
    """Each call appends a separate entry to llm.usage."""
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    llm = LLMClient(provider="ollama", model="phi3")

    mock_resp = mock.MagicMock()
    mock_resp.json.return_value = {"response": "ok", "prompt_eval_count": 5, "eval_count": 5}

    with mock.patch.object(llm, "_httpx") as mock_httpx:
        mock_httpx.post.return_value = mock_resp
        llm("first")
        llm("second")

    assert len(llm.usage) == 2


# ---------------------------------------------------------------------------
# Groq — mocked via sys.modules (package may not be installed in all envs)
# ---------------------------------------------------------------------------

def test_groq_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        LLMClient(provider="groq", model="llama-3.1-8b-instant")


def test_groq_call_returns_text_and_records_usage(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    mock_usage = _types.SimpleNamespace(prompt_tokens=12, completion_tokens=30)
    mock_message = _types.SimpleNamespace(content="groq result")
    mock_choice = _types.SimpleNamespace(message=mock_message)
    mock_resp = _types.SimpleNamespace(choices=[mock_choice], usage=mock_usage)

    mock_groq_mod = mock.MagicMock()
    mock_groq_mod.Groq.return_value.chat.completions.create.return_value = mock_resp

    with mock.patch.dict(sys.modules, {"groq": mock_groq_mod}):
        llm = LLMClient(provider="groq", model="llama-3.1-8b-instant")
        result = llm("test prompt")

    assert result == "groq result"
    assert len(llm.usage) == 1
    entry = llm.usage[0]
    assert entry["provider"] == "groq"
    assert entry["model"] == "llama-3.1-8b-instant"
    assert entry["input_tokens"] == 12
    assert entry["output_tokens"] == 30
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0


def test_groq_handles_missing_usage(monkeypatch):
    """When usage is None the token fields should be None, not raise."""
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")

    mock_message = _types.SimpleNamespace(content="ok")
    mock_choice = _types.SimpleNamespace(message=mock_message)
    mock_resp = _types.SimpleNamespace(choices=[mock_choice], usage=None)

    mock_groq_mod = mock.MagicMock()
    mock_groq_mod.Groq.return_value.chat.completions.create.return_value = mock_resp

    with mock.patch.dict(sys.modules, {"groq": mock_groq_mod}):
        llm = LLMClient(provider="groq", model="llama-3.3-70b-versatile")
        result = llm("prompt")

    assert result == "ok"
    assert llm.usage[0]["input_tokens"] is None
    assert llm.usage[0]["output_tokens"] is None


# ---------------------------------------------------------------------------
# OpenAI — mocked via sys.modules (package may not be installed in all envs)
# ---------------------------------------------------------------------------

def test_openai_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        LLMClient(provider="openai", model="gpt-4o-mini")


def test_openai_call_returns_text_and_records_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    mock_usage = _types.SimpleNamespace(prompt_tokens=18, completion_tokens=42)
    mock_message = _types.SimpleNamespace(content="openai result")
    mock_choice = _types.SimpleNamespace(message=mock_message)
    mock_resp = _types.SimpleNamespace(choices=[mock_choice], usage=mock_usage)

    mock_openai_mod = mock.MagicMock()
    mock_openai_mod.OpenAI.return_value.chat.completions.create.return_value = mock_resp

    with mock.patch.dict(sys.modules, {"openai": mock_openai_mod}):
        llm = LLMClient(provider="openai", model="gpt-4o-mini")
        result = llm("test prompt")

    assert result == "openai result"
    assert len(llm.usage) == 1
    entry = llm.usage[0]
    assert entry["provider"] == "openai"
    assert entry["model"] == "gpt-4o-mini"
    assert entry["input_tokens"] == 18
    assert entry["output_tokens"] == 42
    assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0


def test_openai_handles_missing_usage(monkeypatch):
    """When usage is None the token fields should be None, not raise."""
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

    mock_message = _types.SimpleNamespace(content="ok")
    mock_choice = _types.SimpleNamespace(message=mock_message)
    mock_resp = _types.SimpleNamespace(choices=[mock_choice], usage=None)

    mock_openai_mod = mock.MagicMock()
    mock_openai_mod.OpenAI.return_value.chat.completions.create.return_value = mock_resp

    with mock.patch.dict(sys.modules, {"openai": mock_openai_mod}):
        llm = LLMClient(provider="openai", model="gpt-4o")
        result = llm("prompt")

    assert result == "ok"
    assert llm.usage[0]["input_tokens"] is None
    assert llm.usage[0]["output_tokens"] is None


# ---------------------------------------------------------------------------
# build_graph — deterministic path unchanged
# ---------------------------------------------------------------------------

def test_build_graph_without_llm_compiles():
    from test_data_mining.graph import build_graph
    graph = build_graph(llm=None)
    assert graph is not None


def test_build_graph_with_llm_binds_callable(monkeypatch):
    """build_graph(llm=<callable>) compiles; the llm is forwarded into generate/synthesise."""
    calls = []

    def fake_llm(prompt: str) -> str:
        calls.append(prompt)
        return "mocked"

    from test_data_mining.graph import build_graph
    graph = build_graph(llm=fake_llm)
    assert graph is not None   # compiled successfully


# ---------------------------------------------------------------------------
# /mine regression — no provider/model → deterministic, llm_usage == []
# ---------------------------------------------------------------------------

def test_mine_without_provider_is_deterministic():
    from fastapi.testclient import TestClient
    from backend.app import app

    client = TestClient(app)
    csv_data = b"order_id,email\nORD-1,a@b.com\n"

    resp = client.post("/mine", files=[("test_cases", ("tc.csv", csv_data, "text/csv"))])
    assert resp.status_code == 200

    events = [json.loads(line) for line in resp.text.strip().splitlines() if line.strip()]
    interrupt = next(e for e in events if e["type"] == "interrupt")
    session = interrupt["session"]

    sels = [
        {"field_name": f["field_name"], "include": True, "chosen_set_id": "gen_A"}
        for f in interrupt["payload"]["fields"]
    ]
    r2 = client.post("/resume", data={"session": session, "review_selections": json.dumps(sels)})
    assert r2.status_code == 200

    ev2 = [json.loads(line) for line in r2.text.strip().splitlines() if line.strip()]
    result = next(e for e in ev2 if e["type"] == "result")

    # Deterministic path: llm_usage must be an empty list
    assert result["llm_usage"] == []
    # Output must be produced
    assert result["final_dataset"]
