from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    tokens_used: int


class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> LLMResponse:
        """Send a system+user prompt and return the text response."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a vector embedding for the given text."""


class OpenAIProvider(BaseLLMProvider):
    def __init__(self) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._embed_model = "text-embedding-3-small"

    async def complete(self, system: str, user: str) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            tokens_used=resp.usage.total_tokens if resp.usage else 0,
        )

    async def embed(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(
            model=self._embed_model,
            input=text,
        )
        return resp.data[0].embedding


class AnthropicProvider(BaseLLMProvider):
    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        # Anthropic doesn't have an embedding API; fall back to OpenAI embeddings
        from openai import AsyncOpenAI
        self._embed_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def complete(self, system: str, user: str) -> LLMResponse:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text if resp.content else ""
        tokens = (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0
        return LLMResponse(content=text, tokens_used=tokens)

    async def embed(self, text: str) -> list[float]:
        resp = await self._embed_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return resp.data[0].embedding


def get_llm_provider() -> BaseLLMProvider:
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider == "anthropic":
        return AnthropicProvider()
    return OpenAIProvider()
