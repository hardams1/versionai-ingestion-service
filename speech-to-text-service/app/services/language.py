from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

WHISPER_LANG_TO_ISO: dict[str, str] = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "arabic": "ar",
    "chinese": "zh",
    "hindi": "hi",
    "portuguese": "pt",
    "bengali": "bn",
    "russian": "ru",
    "japanese": "ja",
    "yoruba": "yo",
}


def normalize_language_code(whisper_lang: str) -> str:
    """Convert Whisper's language name/code to ISO 639-1.

    Whisper sometimes returns full names ('english') and sometimes
    ISO codes ('en'). This normalizes to ISO 639-1.
    """
    lower = whisper_lang.lower().strip()

    if len(lower) <= 3:
        return lower

    return WHISPER_LANG_TO_ISO.get(lower, lower[:2])
