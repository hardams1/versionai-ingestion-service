from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

CATEGORIZE_PROMPT = """You are a question categorizer. Given a question asked to a person, classify it into exactly one of these categories:

{categories}

Respond with ONLY valid JSON: {{"category": "<chosen category>", "confidence": <0.0-1.0>}}

Question: {question}"""


class CategorizationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._categories = settings.default_categories

    async def categorize(self, question: str) -> tuple[str, float]:
        """Categorize a question. Returns (category, confidence).

        Falls back to keyword matching if the LLM call fails.
        """
        if self._settings.openai_api_key:
            result = await self._categorize_llm(question)
            if result:
                return result

        return self._categorize_keyword(question)

    async def _categorize_llm(self, question: str) -> Optional[tuple[str, float]]:
        categories_str = "\n".join(f"- {c}" for c in self._categories)
        prompt = CATEGORIZE_PROMPT.format(categories=categories_str, question=question)

        try:
            async with httpx.AsyncClient(timeout=self._settings.categorization_timeout) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._settings.openai_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 64,
                    },
                )
                if resp.status_code != 200:
                    logger.warning("OpenAI categorization returned %d", resp.status_code)
                    return None

                content = resp.json()["choices"][0]["message"]["content"].strip()
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if not match:
                    return None
                data = json.loads(match.group())
                category = data.get("category", "Misc")
                confidence = float(data.get("confidence", 0.5))

                if category not in self._categories:
                    category = "Misc"

                return category, confidence
        except Exception as exc:
            logger.warning("LLM categorization failed: %s", exc)
            return None

    def _categorize_keyword(self, question: str) -> tuple[str, float]:
        q = question.lower()
        keyword_map = {
            "Personal Life": ["family", "childhood", "growing up", "parents", "siblings", "home"],
            "Career": ["job", "work", "career", "profession", "business", "company", "office"],
            "Relationships": ["love", "dating", "marriage", "partner", "relationship", "friend"],
            "Finance": ["money", "invest", "salary", "income", "budget", "financial", "wealth"],
            "Beliefs": ["believe", "religion", "faith", "god", "spiritual", "philosophy", "value"],
            "Education": ["school", "university", "study", "degree", "learn", "college", "education"],
            "Health": ["health", "exercise", "diet", "fitness", "mental", "medical", "wellness"],
            "Hobbies": ["hobby", "fun", "enjoy", "passion", "sport", "music", "art", "game"],
            "Travel": ["travel", "trip", "country", "visit", "vacation", "destination", "flight"],
        }

        best_cat = "Misc"
        best_score = 0

        for category, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > best_score:
                best_score = score
                best_cat = category

        confidence = min(0.8, 0.3 + best_score * 0.15) if best_score > 0 else 0.2
        return best_cat, confidence
