from __future__ import annotations

import logging
from typing import Optional

from app.core.config import Settings
from app.models.schemas import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class LanguageService:
    LANG_MAP = SUPPORTED_LANGUAGES

    def __init__(self, settings: Settings) -> None:
        self._openai_key = settings.openai_api_key

    def detect(self, text: str) -> tuple[str, float]:
        """Return (language_code, confidence). Falls back to 'en'."""
        try:
            from langdetect import detect_langs

            results = detect_langs(text)
            if results:
                best = results[0]
                code = str(best.lang)
                if code in ("zh-cn", "zh-tw"):
                    code = "zh"
                return code, best.prob
        except Exception as e:
            logger.debug("Language detection failed: %s", e)
        return "en", 1.0

    async def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        """Translate text using OpenAI GPT. Returns translated text."""
        if not text.strip():
            return text

        src = source_lang or "auto-detected"
        if src == target_lang:
            return text

        src_name = self.LANG_MAP.get(src, src)
        tgt_name = self.LANG_MAP.get(target_lang, target_lang)

        if not self._openai_key:
            logger.warning("OpenAI key not set, returning original text")
            return text

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._openai_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    f"You are a translator. Translate the following text from {src_name} to {tgt_name}. "
                                    f"Preserve the original tone and meaning. "
                                    f"For Nigerian Pidgin (pcm), use authentic Pidgin English. "
                                    f"For Yoruba (yo), use proper Yoruba. "
                                    f"Return ONLY the translated text, nothing else."
                                ),
                            },
                            {"role": "user", "content": text},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("Translation failed: %s", e)
            return text
