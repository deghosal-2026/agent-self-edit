"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Raised when an LLM provider call fails (timeout, rate limit, network)."""


class LLMProvider(ABC):
    """A minimal LLM interface used for all agent + judge calls."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        """Return the model's completion for ``prompt``.

        Raises :class:`ProviderError` on failure.
        """
        raise NotImplementedError
