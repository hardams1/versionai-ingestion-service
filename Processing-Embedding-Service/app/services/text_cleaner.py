from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class TextCleaner:
    """Cleans and normalizes extracted text for downstream processing."""

    def clean(self, text: str, max_length: int = 5_000_000) -> str:
        if not text:
            return ""

        original_len = len(text)

        text = self._normalize_unicode(text)
        text = self._fix_encoding_artifacts(text)
        text = self._normalize_whitespace(text)
        text = self._remove_control_chars(text)
        text = self._collapse_newlines(text)
        text = text.strip()

        if len(text) > max_length:
            logger.warning(
                "Text truncated from %d to %d characters", len(text), max_length
            )
            text = text[:max_length]

        logger.info("Cleaned text: %d -> %d characters", original_len, len(text))
        return text

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def _fix_encoding_artifacts(text: str) -> str:
        replacements = {
            "\u00e2\u0080\u0099": "'",
            "\u00e2\u0080\u009c": '"',
            "\u00e2\u0080\u009d": '"',
            "\u00e2\u0080\u0093": "–",
            "\u00e2\u0080\u0094": "—",
            "\u00c2\u00a0": " ",
            "\ufffd": "",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        text = text.replace("\t", "    ")
        text = re.sub(r"[^\S\n]+", " ", text)
        return text

    @staticmethod
    def _remove_control_chars(text: str) -> str:
        return "".join(
            ch for ch in text
            if ch == "\n" or ch == "\r" or not unicodedata.category(ch).startswith("C")
        )

    @staticmethod
    def _collapse_newlines(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text
