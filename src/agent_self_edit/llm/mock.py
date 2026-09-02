"""Mock LLM provider for hermetic CI and tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import LLMProvider, ProviderError


class MockProvider(LLMProvider):
    """Returns predetermined responses; never makes a real LLM call.

    ``responses`` may be:
    - a callable ``(prompt, system_prompt) -> str``
    - a dict mapping a prompt substring/suffix to an output
    - a flat list used round-robin
    - a plain string used as the answer for every prompt
    """

    def __init__(
        self,
        responses: Any = "mock output",
        model: str = "mock-model",
    ) -> None:
        if isinstance(responses, list) and not responses:
            raise ProviderError("MockProvider requires at least one response when using a list")
        self._responses = responses
        self.model = model
        self.calls: list[dict[str, str]] = []

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        responses = self._responses

        if callable(responses):
            return str(responses(prompt, system_prompt))

        if isinstance(responses, list):
            index = len(self.calls) - 1
            return str(responses[index % len(responses)])

        if isinstance(responses, dict):
            for key, value in responses.items():
                if key in prompt:
                    return str(value)
            return ""

        return str(responses)


class DeterministicCallable:
    """Helper wrapping a plain function into the MockProvider contract."""

    def __init__(self, fn: Callable[[str, str], str]) -> None:
        self._fn = fn

    def __call__(self, prompt: str, system_prompt: str = "") -> str:
        return self._fn(prompt, system_prompt)
