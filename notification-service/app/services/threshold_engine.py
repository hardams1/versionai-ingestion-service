from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)

THRESHOLDS = [100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]


def check_threshold(count: int, last_threshold: int) -> int | None:
    """Return the threshold that was just crossed, or None."""
    for t in THRESHOLDS:
        if count >= t and last_threshold < t:
            return t
    return None


async def get_last_threshold(db: aiosqlite.Connection, user_id: str, category: str) -> int:
    cursor = await db.execute(
        "SELECT last_threshold FROM threshold_state WHERE user_id = ? AND category = ?",
        (user_id, category),
    )
    row = await cursor.fetchone()
    return row["last_threshold"] if row else 0


async def set_last_threshold(db: aiosqlite.Connection, user_id: str, category: str, threshold: int) -> None:
    await db.execute(
        """INSERT INTO threshold_state (user_id, category, last_threshold)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, category)
           DO UPDATE SET last_threshold = excluded.last_threshold""",
        (user_id, category, threshold),
    )
    await db.commit()


async def evaluate_faq_threshold(
    db: aiosqlite.Connection,
    user_id: str,
    category: str,
    question_count: int,
) -> int | None:
    """Evaluate whether a FAQ category crossed a new threshold. Returns the threshold or None."""
    last = await get_last_threshold(db, user_id, category)
    crossed = check_threshold(question_count, last)
    if crossed:
        await set_last_threshold(db, user_id, category, crossed)
        logger.info(
            "Threshold crossed: user=%s category=%s count=%d threshold=%d",
            user_id, category, question_count, crossed,
        )
    return crossed
