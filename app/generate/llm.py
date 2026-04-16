"""LLM strategy.

The application talks to ``LLMClient`` only. Production uses
``OllamaClient`` (local, free, no API key); tests inject ``StubLLMClient``
which returns canned answers so CI can run without a model server.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.config import get_settings


class LLMClient(Protocol):
    async def generate(self, *, system: str, user: str) -> str: ...
    async def health(self) -> bool: ...


class OllamaClient:
    """Talks to the Ollama HTTP API at /api/chat.

    Streaming is disabled — we want a single string back, and the caller
    can stream over the network themselves if they choose.
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

    async def generate(self, *, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": 0.2, "num_ctx": 4096},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()

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

    async def health(self) -> bool:
        return True
