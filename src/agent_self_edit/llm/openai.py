"""OpenAI-compatible LLM provider."""

from __future__ import annotations

from typing import Any

from .base import LLMProvider, ProviderError

_OPENAI_ERROR = (
    "The 'openai' package is required for the OpenAI provider. "
    "Install with: pip install 'agent-self-edit[llm]'"
)


class OpenAIProvider(LLMProvider):
    """Calls an OpenAI-compatible chat-completions endpoint.

    The client is created lazily so the provider can be constructed in
    hermetic CI without an API key.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI as _OpenAI

            client = _OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        except ImportError as e:
            raise ProviderError(_OPENAI_ERROR) from e
        self._client = client
        return client

    @staticmethod
    def build_messages(prompt: str, system_prompt: str) -> list[dict[str, str]]:
        """Format ``(system_prompt, prompt)`` into chat messages (testable)."""
        if system_prompt:
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        return [{"role": "user", "content": prompt}]

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        messages = self.build_messages(prompt, system_prompt)
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
        except Exception as e:  # noqa: BLE001 - provider exceptions are opaque
            raise ProviderError(str(e)) from e
        choices = response.choices
        if not choices:
            raise ProviderError("OpenAI returned no choices")
        return str(choices[0].message.content or "")
