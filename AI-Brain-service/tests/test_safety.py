from __future__ import annotations

import pytest

from app.models.enums import SafetyVerdict
from app.models.schemas import SourceChunk
from app.services.safety import SafetyProcessor


@pytest.fixture
def safety(settings):
    return SafetyProcessor(settings)


def test_clean_response_passes(safety):
    result = safety.process("This is a safe and helpful answer.")
    assert result.verdict == SafetyVerdict.PASS
    assert result.filtered_response == "This is a safe and helpful answer."
    assert result.flags == []


def test_ssn_pattern_is_redacted(safety):
    result = safety.process("Your SSN is 123-45-6789.")
    assert result.verdict == SafetyVerdict.BLOCKED
    assert "[REDACTED]" in result.filtered_response
    assert any("pattern_match" in f for f in result.flags)


def test_credit_card_is_redacted(safety):
    result = safety.process("Card number: 1234567890123456 on file.")
    assert "[REDACTED]" in result.filtered_response


def test_password_leak_is_redacted(safety):
    result = safety.process("The password: supersecret123 was found.")
    assert "[REDACTED]" in result.filtered_response


def test_long_response_is_truncated(settings):
    settings.safety_max_response_length = 50
    safety = SafetyProcessor(settings)
    long_text = "word " * 100
    result = safety.process(long_text)
    assert len(result.filtered_response) <= 55
    assert "truncated" in result.flags


def test_citation_without_context_flagged(safety):
    result = safety.process(
        "According to the document, the answer is 42.",
        context_chunks=[],
    )
    assert "grounding:citation_without_context" in result.flags


def test_citation_with_context_not_flagged(safety):
    chunks = [SourceChunk(text="The answer is 42.", score=0.9)]
    result = safety.process(
        "According to the document, the answer is 42.",
        context_chunks=chunks,
    )
    assert "grounding:citation_without_context" not in result.flags


def test_multiple_patterns_all_redacted(safety):
    text = "SSN: 123-45-6789 and password: hunter2 found."
    result = safety.process(text)
    assert result.filtered_response.count("[REDACTED]") >= 2
    assert result.verdict == SafetyVerdict.BLOCKED


def test_empty_response_passes(safety):
    result = safety.process("")
    assert result.verdict == SafetyVerdict.PASS
