"""Tests for the LLM provider layer."""

import pytest

from agent_self_edit.llm import MockProvider, OpenAIProvider, ProviderError
from agent_self_edit.llm.base import LLMProvider


class FailingProvider(LLMProvider):
    def complete(self, prompt, system_prompt="", temperature=0.0):
        raise ProviderError("timeout")


class SlowProvider(LLMProvider):
    def __init__(self, delay_ms=5):
        self.delay_ms = delay_ms

    def complete(self, prompt, system_prompt="", temperature=0.0):
        import time
        time.sleep(self.delay_ms / 1000)
        return "ok"


def test_mock_returns_plain_string():
    p = MockProvider(responses="fixed answer")
    assert p.complete("q") == "fixed answer"


def test_mock_round_robin_list():
    p = MockProvider(responses=["a", "b", "c"])
    assert p.complete("q1") == "a"
    assert p.complete("q2") == "b"
    assert p.complete("q3") == "c"
    assert p.complete("q4") == "a"


def test_mock_dict_match():
    p = MockProvider(responses={"classify": "cat", "extract": "date"})
    assert p.complete("Please classify this") == "cat"
    assert p.complete("extract the fields") == "date"
    assert p.complete("unknown") == ""


def test_mock_callable():
    p = MockProvider(responses=lambda prompt, sp: f"echo:{sp}")
    assert p.complete("q", system_prompt="sys") == "echo:sys"


def test_mock_tracks_calls():
    p = MockProvider(responses="x")
    p.complete("q1", system_prompt="s1")
    p.complete("q2")
    assert len(p.calls) == 2
    assert p.calls[0]["system_prompt"] == "s1"


def test_abstract_cannot_instantiate():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_failing_provider_raises():
    p = FailingProvider()
    with pytest.raises(ProviderError):
        p.complete("q")


def test_openai_build_messages_with_system():
    msgs = OpenAIProvider.build_messages("body", "sys")
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "body"},
    ]


def test_openai_build_messages_without_system():
    msgs = OpenAIProvider.build_messages("body", "")
    assert msgs == [{"role": "user", "content": "body"}]


def test_openai_missing_package_raises_provider_error(monkeypatch):
    # Simulate missing openai package by monkeypatching module import
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    p = OpenAIProvider("gpt-4o-mini", api_key="k")
    with pytest.raises(ProviderError):
        p.complete("hello")
