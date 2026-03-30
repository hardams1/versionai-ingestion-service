from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.models.enums import SafetyVerdict
from app.models.schemas import SourceChunk

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class SafetyResult:
    __slots__ = ("verdict", "filtered_response", "flags")

    def __init__(self, verdict: SafetyVerdict, filtered_response: str, flags: list[str] | None = None) -> None:
        self.verdict = verdict
        self.filtered_response = filtered_response
        self.flags = flags or []


class SafetyProcessor:
    """
    Post-processes LLM output for safety and grounding:
    1. Strips leaked PII / sensitive patterns.
    2. Truncates overly long responses.
    3. Validates response is grounded in provided context.
    """

    def __init__(self, settings: Settings) -> None:
        self._max_length = settings.safety_max_response_length
        self._block_patterns = [re.compile(p) for p in settings.safety_block_patterns]

    def process(
        self, response: str, context_chunks: list[SourceChunk] | None = None
    ) -> SafetyResult:
        flags: list[str] = []
        filtered = response

        filtered, pii_flags = self._scrub_sensitive(filtered)
        flags.extend(pii_flags)

        if len(filtered) > self._max_length:
            filtered = filtered[: self._max_length].rsplit(" ", 1)[0] + "..."
            flags.append("truncated")

        grounding_flags = self._check_grounding(filtered, context_chunks or [])
        flags.extend(grounding_flags)

        if any(f.startswith("blocked:") for f in flags):
            verdict = SafetyVerdict.BLOCKED
        elif flags:
            verdict = SafetyVerdict.FILTERED
        else:
            verdict = SafetyVerdict.PASS

        if verdict != SafetyVerdict.PASS:
            logger.warning("Safety flags: %s", flags)

        return SafetyResult(verdict=verdict, filtered_response=filtered, flags=flags)

    def _scrub_sensitive(self, text: str) -> tuple[str, list[str]]:
        flags: list[str] = []
        result = text
        for pattern in self._block_patterns:
            if pattern.search(result):
                result = pattern.sub("[REDACTED]", result)
                flags.append(f"blocked:pattern_match:{pattern.pattern[:30]}")
        return result, flags

    def _check_grounding(self, response: str, context_chunks: list[SourceChunk]) -> list[str]:
        """
        Light heuristic grounding check: flag responses that make specific
        claims while no context was provided.
        """
        flags: list[str] = []

        if not context_chunks:
            citation_patterns = [
                r"(?i)according to",
                r"(?i)the (?:document|file|source|text) (?:states|says|mentions|indicates)",
                r"(?i)as (?:stated|mentioned|described) in",
            ]
            for pattern in citation_patterns:
                if re.search(pattern, response):
                    flags.append("grounding:citation_without_context")
                    break

        return flags
