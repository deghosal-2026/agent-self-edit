"""OpenAI-compatible LLM provider."""

from __future__ import annotations

import json
import os
import time
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

    ``extra_body`` is configurable per-role (defaults to
    ``{"chat_template_kwargs": {"enable_thinking": False}}`` for
    backends that need it). Set to ``None`` or ``{}`` to omit.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_tokens: int = 2048,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._extra_body = extra_body
        self._client: Any | None = None
        self._traffic_log = os.environ.get("AGENT_SELF_EDIT_LLM_LOG")

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

    def _log_traffic(self, entry: dict[str, Any]) -> None:
        if not self._traffic_log:
            return
        try:
            with open(self._traffic_log, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass

    def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
    ) -> str:
        messages = self.build_messages(prompt, system_prompt)
        client = self._get_client()
        t0 = time.time()
        response = None
        try:
            kwargs: dict[str, Any] = dict(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=self._max_tokens,
            )
            if self._extra_body:
                kwargs["extra_body"] = self._extra_body
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            self._log_traffic({
                "model": self.model,
                "base_url": self._base_url,
                "messages": messages,
                "temperature": temperature,
                "error": str(e),
                "latency_ms": int((time.time() - t0) * 1000),
            })
            raise ProviderError(str(e)) from e
        latency_ms = int((time.time() - t0) * 1000)
        choices = response.choices
        if not choices:
            self._log_traffic({
                "model": self.model,
                "base_url": self._base_url,
                "messages": messages,
                "temperature": temperature,
                "response": str(response),
                "error": "no choices returned",
                "latency_ms": latency_ms,
            })
            raise ProviderError("OpenAI returned no choices")

        content = str(choices[0].message.content or "")

        usage = getattr(response, "usage", None)
        self._log_traffic({
            "model": self.model,
            "base_url": self._base_url,
            "messages": messages,
            "temperature": temperature,
            "response": content,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            } if usage else None,
            "latency_ms": latency_ms,
        })
        return content
