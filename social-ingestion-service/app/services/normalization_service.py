from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "politics": ["election", "government", "policy", "political", "congress", "senate", "vote", "democrat", "republican", "president"],
    "sports": ["game", "team", "score", "player", "match", "championship", "league", "football", "basketball", "soccer"],
    "finance": ["stock", "market", "invest", "bitcoin", "crypto", "money", "trading", "economy", "bank", "revenue"],
    "technology": ["ai", "software", "tech", "startup", "coding", "algorithm", "data", "cloud", "api"],
    "relationships": ["love", "dating", "marriage", "relationship", "partner", "breakup", "couple", "romance"],
    "health": ["health", "fitness", "workout", "diet", "mental", "wellness", "exercise", "medical", "nutrition"],
    "entertainment": ["movie", "music", "show", "concert", "album", "streaming", "celebrity", "film", "series"],
    "food": ["recipe", "cooking", "restaurant", "food", "meal", "chef", "cuisine", "eat", "delicious"],
    "travel": ["travel", "trip", "vacation", "flight", "hotel", "destination", "adventure", "explore"],
    "education": ["school", "university", "study", "learn", "degree", "course", "student", "teacher", "education"],
}


_MULTI_WORD_TOPICS = {
    "technology": ["machine learning"],
}


def extract_topics(text: str) -> List[str]:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    lower_text = text.lower()
    found = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in words for kw in keywords):
            found.append(topic)
            continue
        for phrase in _MULTI_WORD_TOPICS.get(topic, []):
            if phrase in lower_text:
                found.append(topic)
                break
    return found or ["general"]


def extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#(\w+)", text)


def extract_mentions(text: str) -> List[str]:
    return re.findall(r"@(\w+)", text)


def compute_writing_style(texts: List[str]) -> dict:
    """Analyze writing style from a collection of posts."""
    if not texts:
        return {"avg_length": 0, "emoji_usage": "none", "formality": "unknown"}

    total_len = sum(len(t) for t in texts)
    avg_len = total_len / len(texts)

    emoji_count = sum(1 for t in texts for c in t if ord(c) > 0x1F600)
    emoji_usage = "high" if emoji_count > len(texts) else "moderate" if emoji_count > 0 else "none"

    formal_words = ["therefore", "furthermore", "consequently", "however", "nevertheless"]
    informal_words = ["lol", "omg", "tbh", "ngl", "bruh", "gonna", "wanna"]

    all_text = " ".join(texts).lower()
    formal_hits = sum(1 for w in formal_words if w in all_text)
    informal_hits = sum(1 for w in informal_words if w in all_text)

    if formal_hits > informal_hits:
        formality = "formal"
    elif informal_hits > formal_hits:
        formality = "casual"
    else:
        formality = "neutral"

    return {
        "avg_length": round(avg_len),
        "emoji_usage": emoji_usage,
        "formality": formality,
    }
