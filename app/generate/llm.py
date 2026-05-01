"""LLM strategy.

The application talks to ``LLMClient`` only. Production uses
``OllamaClient`` (local, free, no API key); tests inject ``StubLLMClient``
which returns canned answers so CI can run without a model server.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.config import get_settings


class LLMClient(Protocol):
    async def generate(self, *, system: str, user: str) -> str: ...
    async def stream(self, *, system: str, user: str) -> AsyncIterator[str]: ...
    async def health(self) -> bool: ...


class OllamaClient:
    """Talks to the Ollama HTTP API at /api/chat.

    ``generate()`` returns the full answer as a single string.
    ``stream()`` yields incremental token chunks for SSE responses.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        s = get_settings()
        self._base_url = (base_url or s.ollama_base_url).rstrip("/")
        self._model = model or s.ollama_model
        self._timeout = timeout_s or s.llm_timeout_s

    def _payload(self, system: str, user: str, *, stream: bool) -> dict:
        return {
            "model": self._model,
            "stream": stream,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.2, "num_ctx": 4096},
        }

    async def generate(self, *, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json=self._payload(system, user, stream=False),
            )
            resp.raise_for_status()
            data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()

    async def stream(self, *, system: str, user: str) -> AsyncIterator[str]:
        """Yield incremental answer tokens from Ollama's NDJSON stream."""
        async with httpx.AsyncClient(timeout=self._timeout) as client, client.stream(
            "POST",
            f"{self._base_url}/api/chat",
            json=self._payload(system, user, stream=True),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = (obj.get("message") or {}).get("content", "")
                if piece:
                    yield piece
                if obj.get("done"):
                    return

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False


class StubLLMClient:
    """Echo client for tests. Records the last prompt it saw."""

    def __init__(self, answer: str = "stub answer [chunk:1]") -> None:
        self._answer = answer
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def generate(self, *, system: str, user: str) -> str:
        self.last_system = system
        self.last_user = user
        return self._answer

    async def stream(self, *, system: str, user: str) -> AsyncIterator[str]:
        self.last_system = system
        self.last_user = user
        # Emit the canned answer in two chunks so streaming tests are real.
        mid = max(1, len(self._answer) // 2)
        yield self._answer[:mid]
        yield self._answer[mid:]

    async def health(self) -> bool:
        return True
