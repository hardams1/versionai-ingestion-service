from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.models.schemas import TokenUsage
from app.utils.exceptions import LLMError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    @abstractmethod
    async def generate(
        self, messages: list[dict[str, str]], temperature: float | None = None, max_tokens: int | None = None
    ) -> LLMResponse: ...

    @abstractmethod
    def model_name(self) -> str: ...

    async def health_check(self) -> bool:
        return True


class LLMResponse:
    __slots__ = ("content", "model", "usage", "finish_reason")

    def __init__(
        self,
        content: str,
        model: str,
        usage: TokenUsage | None = None,
        finish_reason: str | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.usage = usage
        self.finish_reason = finish_reason


async def _retry_with_backoff(coro_factory, max_retries: int, base_delay: float, timeout: float):
    """Execute an async callable with exponential backoff and timeout."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(coro_factory(), timeout=timeout)
        except asyncio.TimeoutError:
            last_exc = LLMError(f"LLM call timed out after {timeout}s (attempt {attempt + 1})")
            logger.warning("LLM timeout on attempt %d/%d", attempt + 1, max_retries + 1)
        except LLMError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM call failed on attempt %d/%d: %s", attempt + 1, max_retries + 1, exc)

        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            logger.info("Retrying LLM call in %.1fs...", delay)
            await asyncio.sleep(delay)

    raise LLMError(f"LLM call failed after {max_retries + 1} attempts: {last_exc}") from last_exc


class OpenAILLM(BaseLLM):
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is required when llm_provider=openai")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMError("openai package is required") from exc

        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        self._model = settings.openai_model
        self._temperature = settings.openai_temperature
        self._max_tokens = settings.openai_max_tokens
        self._timeout = settings.llm_timeout_seconds
        self._max_retries = settings.llm_max_retries
        self._retry_delay = settings.llm_retry_base_delay

    def model_name(self) -> str:
        return self._model

    async def generate(
        self, messages: list[dict[str, str]], temperature: float | None = None, max_tokens: int | None = None
    ) -> LLMResponse:
        async def _call():
            return await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature if temperature is not None else self._temperature,
                max_tokens=max_tokens or self._max_tokens,
            )

        try:
            response = await _retry_with_backoff(
                _call, self._max_retries, self._retry_delay, self._timeout,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"OpenAI API error: {exc}") from exc

        choice = response.choices[0]
        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        logger.info(
            "OpenAI response: model=%s, tokens=%s, finish=%s",
            response.model,
            response.usage.total_tokens if response.usage else "?",
            choice.finish_reason,
        )

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
        )


class DemoLLM(BaseLLM):
    """Returns plausible canned responses so the full pipeline works without an API key."""

    def model_name(self) -> str:
        return "demo-mode"

    async def generate(
        self, messages: list[dict[str, str]], temperature: float | None = None, max_tokens: int | None = None
    ) -> LLMResponse:
        user_query = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_query = msg["content"]
                break

        content = (
            f"[Demo Mode] I received your question. "
            f"In production, this would be answered by the configured LLM provider. "
            f"Your query was: \"{user_query[:200]}\" — "
            f"To enable real responses, set a valid OPENAI_API_KEY or ANTHROPIC_API_KEY "
            f"in AI-Brain-service/.env and restart the service."
        )

        logger.info("DemoLLM generated response for query length=%d", len(user_query))
        return LLMResponse(content=content, model="demo-mode", usage=None, finish_reason="stop")


class AnthropicLLM(BaseLLM):
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")

        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise LLMError("anthropic package is required") from exc

        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        self._model = settings.anthropic_model
        self._temperature = settings.anthropic_temperature
        self._max_tokens = settings.anthropic_max_tokens
        self._timeout = settings.llm_timeout_seconds
        self._max_retries = settings.llm_max_retries
        self._retry_delay = settings.llm_retry_base_delay

    def model_name(self) -> str:
        return self._model

    async def generate(
        self, messages: list[dict[str, str]], temperature: float | None = None, max_tokens: int | None = None
    ) -> LLMResponse:
        system_content = ""
        filtered_messages: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                filtered_messages.append(msg)

        async def _call():
            return await self._client.messages.create(
                model=self._model,
                system=system_content.strip() or None,
                messages=filtered_messages,
                temperature=temperature if temperature is not None else self._temperature,
                max_tokens=max_tokens or self._max_tokens,
            )

        try:
            response = await _retry_with_backoff(
                _call, self._max_retries, self._retry_delay, self._timeout,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        usage = TokenUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

        logger.info(
            "Anthropic response: model=%s, tokens=%d, stop=%s",
            response.model,
            usage.total_tokens,
            response.stop_reason,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
            finish_reason=response.stop_reason,
        )
