"""Coverage completion tests for OpenAIProvider (all uncovered lines)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent_self_edit.llm import OpenAIProvider
from agent_self_edit.llm.base import ProviderError


def _make_choice(content: str = "hello world") -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    return choice


def _make_response(choices: list[MagicMock] | None = None, usage: MagicMock | None = None) -> MagicMock:
    resp = MagicMock()
    resp.choices = [_make_choice()] if choices is None else choices
    resp.usage = usage
    return resp


# ── __init__ fields ───────────────────────────────────────────────────────────


def test_init_defaults() -> None:
    p = OpenAIProvider(api_key="sk-test")
    assert p.model == "gpt-4o-mini"
    assert p._api_key == "sk-test"
    assert p._base_url is None
    assert p._timeout == 30.0
    assert p._max_tokens == 2048
    assert p._extra_body is None
    assert p._client is None


def test_init_custom_values() -> None:
    p = OpenAIProvider(
        model="gpt-4",
        api_key="sk-custom",
        base_url="https://custom.example.com/v1",
        timeout=60.0,
        max_tokens=4096,
        extra_body={"foo": "bar"},
    )
    assert p.model == "gpt-4"
    assert p._api_key == "sk-custom"
    assert p._base_url == "https://custom.example.com/v1"
    assert p._timeout == 60.0
    assert p._max_tokens == 4096
    assert p._extra_body == {"foo": "bar"}


# ── _get_client (lines 47-61) ────────────────────────────────────────────────


@patch("openai.OpenAI")
def test_get_client_creates_and_caches(mock_openai_class: MagicMock) -> None:
    mock_instance = MagicMock()
    mock_openai_class.return_value = mock_instance

    p = OpenAIProvider(api_key="sk-test")
    client1 = p._get_client()
    client2 = p._get_client()

    assert client1 is mock_instance
    assert client2 is mock_instance
    mock_openai_class.assert_called_once_with(
        api_key="sk-test",
        base_url=None,
        timeout=30.0,
    )


@patch("openai.OpenAI")
def test_get_client_returns_cached(mock_openai_class: MagicMock) -> None:
    mock_instance = MagicMock()
    mock_openai_class.return_value = mock_instance

    p = OpenAIProvider(api_key="sk-test")
    p._client = mock_instance  # pre-set cached value

    result = p._get_client()
    assert result is mock_instance
    mock_openai_class.assert_not_called()


# ── _log_traffic (lines 73-80) ──────────────────────────────────────────────


def test_log_traffic_noop_when_env_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_SELF_EDIT_LLM_LOG", raising=False)
    p = OpenAIProvider(api_key="sk-test")
    p._log_traffic({"key": "value"})  # should not raise


def test_log_traffic_writes_to_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    log_file = tmp_path / "traffic.log"
    monkeypatch.setenv("AGENT_SELF_EDIT_LLM_LOG", str(log_file))
    p = OpenAIProvider(api_key="sk-test")

    p._log_traffic({"msg": "hello"})
    content = log_file.read_text().strip()
    assert json.loads(content) == {"msg": "hello"}


def test_log_traffic_silent_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SELF_EDIT_LLM_LOG", "/nonexistent/deep/dir/traffic.log")
    p = OpenAIProvider(api_key="sk-test")
    p._log_traffic({"msg": "hello"})  # should not raise


# ── complete() success path (lines 90-142) ────────────────────────────────────


@patch("openai.OpenAI")
def test_complete_success(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    resp = _make_response()
    mock_client.chat.completions.create.return_value = resp

    p = OpenAIProvider(api_key="sk-test")
    result = p.complete("hello", system_prompt="be helpful")

    assert result == "hello world"
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["messages"] == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "hello"},
    ]
    assert kwargs["temperature"] == 0.0
    assert kwargs["max_tokens"] == 2048


@patch("openai.OpenAI")
def test_complete_with_extra_body(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_response()

    p = OpenAIProvider(api_key="sk-test", extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    p.complete("hello")

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


@patch("openai.OpenAI")
def test_complete_empty_extra_body_omitted(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_response()

    p = OpenAIProvider(api_key="sk-test", extra_body={})
    p.complete("hello")

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert "extra_body" not in kwargs


@patch("openai.OpenAI")
def test_complete_uses_temperature(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_response()

    p = OpenAIProvider(api_key="sk-test")
    p.complete("hello", temperature=0.7)

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["temperature"] == 0.7


# ── complete() with usage info ───────────────────────────────────────────────


@patch("openai.OpenAI")
def test_complete_with_usage(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    usage.total_tokens = 30
    mock_client.chat.completions.create.return_value = _make_response(usage=usage)

    p = OpenAIProvider(api_key="sk-test")
    result = p.complete("hello")
    assert result == "hello world"


# ── complete() error paths ────────────────────────────────────────────────────


@patch("openai.OpenAI")
def test_complete_no_choices_raises(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _make_response(choices=[])

    p = OpenAIProvider(api_key="sk-test")
    with pytest.raises(ProviderError, match="OpenAI returned no choices"):
        p.complete("hello")


@patch("openai.OpenAI")
def test_complete_api_error_raises(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("connection timeout")

    p = OpenAIProvider(api_key="sk-test")
    with pytest.raises(ProviderError, match="connection timeout"):
        p.complete("hello")


@patch("openai.OpenAI")
def test_complete_rate_limit_error_raises(mock_openai_class: MagicMock) -> None:
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")

    p = OpenAIProvider(api_key="sk-test")
    with pytest.raises(ProviderError, match="Rate limit exceeded"):
        p.complete("hello")


def test_complete_traffic_log_on_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    log_file = tmp_path / "error_traffic.log"
    monkeypatch.setenv("AGENT_SELF_EDIT_LLM_LOG", str(log_file))
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("boom")

        p = OpenAIProvider(api_key="sk-test")
        with pytest.raises(ProviderError):
            p.complete("hello")

    content = log_file.read_text().strip()
    entry = json.loads(content)
    assert entry["error"] == "boom"
    assert "latency_ms" in entry


def test_complete_traffic_log_on_no_choices(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    log_file = tmp_path / "no_choices.log"
    monkeypatch.setenv("AGENT_SELF_EDIT_LLM_LOG", str(log_file))
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response(choices=[])

        p = OpenAIProvider(api_key="sk-test")
        with pytest.raises(ProviderError):
            p.complete("hello")

    content = log_file.read_text().strip()
    entry = json.loads(content)
    assert entry["error"] == "no choices returned"


def test_complete_traffic_log_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    log_file = tmp_path / "success.log"
    monkeypatch.setenv("AGENT_SELF_EDIT_LLM_LOG", str(log_file))
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_response()

        p = OpenAIProvider(api_key="sk-test")
        p.complete("hello")

    content = log_file.read_text().strip()
    entry = json.loads(content)
    assert entry["response"] == "hello world"
    assert "usage" in entry
    assert "latency_ms" in entry


# ── build_messages (static) ───────────────────────────────────────────────────


def test_build_messages_with_system() -> None:
    msgs = OpenAIProvider.build_messages("body", "sys")
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "body"},
    ]


def test_build_messages_without_system() -> None:
    msgs = OpenAIProvider.build_messages("body", "")
    assert msgs == [{"role": "user", "content": "body"}]


# ── edge: missing openai package ──────────────────────────────────────────────


def test_missing_openai_package_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    p = OpenAIProvider(api_key="sk-test")
    with pytest.raises(ProviderError, match="openai.*package.*required"):
        p.complete("hello")
