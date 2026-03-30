from __future__ import annotations

import asyncio

import pytest

from app.services.llm import _retry_with_backoff, LLMResponse
from app.utils.exceptions import LLMError


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt():
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await _retry_with_backoff(factory, max_retries=3, base_delay=0.01, timeout=5.0)
    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_succeeds_after_failure():
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")
        return "recovered"

    result = await _retry_with_backoff(factory, max_retries=3, base_delay=0.01, timeout=5.0)
    assert result == "recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_raises_after_exhaustion():
    async def factory():
        raise ConnectionError("permanent")

    with pytest.raises(LLMError, match="failed after"):
        await _retry_with_backoff(factory, max_retries=2, base_delay=0.01, timeout=5.0)


@pytest.mark.asyncio
async def test_retry_timeout():
    async def factory():
        await asyncio.sleep(10)

    with pytest.raises(LLMError, match="failed after"):
        await _retry_with_backoff(factory, max_retries=1, base_delay=0.01, timeout=0.1)


@pytest.mark.asyncio
async def test_retry_does_not_catch_llm_error():
    async def factory():
        raise LLMError("explicit error")

    with pytest.raises(LLMError, match="explicit error"):
        await _retry_with_backoff(factory, max_retries=3, base_delay=0.01, timeout=5.0)
