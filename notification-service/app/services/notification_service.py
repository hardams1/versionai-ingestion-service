from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from app.db import get_db
from app.models.notification import (
    IncomingEvent,
    NotificationCategory,
)
from app.services.delivery_service import deliver
from app.services.event_router import route_event
from app.services.threshold_engine import evaluate_faq_threshold

logger = logging.getLogger(__name__)

CATEGORY_PREF_MAP = {
    NotificationCategory.SOCIAL: "follow_notifications",
    NotificationCategory.FAQ: "faq_notifications",
    NotificationCategory.VIRAL: "viral_notifications",
    NotificationCategory.AI_EVOLUTION: "ai_evolution_notifications",
}


async def _check_user_pref(db: aiosqlite.Connection, user_id: str, category: NotificationCategory) -> bool:
    pref_col = CATEGORY_PREF_MAP.get(category)
    if not pref_col:
        return True
    cursor = await db.execute(
        f"SELECT {pref_col} FROM notification_preferences WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return True
    return bool(row[pref_col])


async def process_event(event: IncomingEvent) -> Optional[dict[str, Any]]:
    """Process an incoming event: route, check prefs/idempotency, store, deliver."""
    db = await get_db()
    try:
        # Idempotency check
        if event.idempotency_key:
            cursor = await db.execute(
                "SELECT id FROM notifications WHERE idempotency_key = ?",
                (event.idempotency_key,),
            )
            if await cursor.fetchone():
                logger.info("Duplicate event skipped: key=%s", event.idempotency_key)
                return None

        # FAQ threshold sub-processing
        if event.event_type == "faq_category_updated":
            cat_name = event.payload.get("category", "General")
            count = event.payload.get("question_count", 0)
            threshold = await evaluate_faq_threshold(db, event.user_id, cat_name, count)
            if threshold:
                event = IncomingEvent(
                    event_type="faq_threshold",
                    user_id=event.user_id,
                    payload={**event.payload, "count": threshold},
                    idempotency_key=f"faq-threshold-{event.user_id}-{cat_name}-{threshold}",
                )
            else:
                return None

        title, message, category, priority = route_event(event.event_type, event.payload)

        if not await _check_user_pref(db, event.user_id, category):
            logger.info("Notification suppressed by user preference: user=%s type=%s", event.user_id, event.event_type)
            return None

        notif_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await db.execute(
            """INSERT INTO notifications
               (id, user_id, type, category, title, message, priority, status, idempotency_key, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'unread', ?, ?, ?)""",
            (
                notif_id, event.user_id, event.event_type, category.value,
                title, message, priority.value,
                event.idempotency_key,
                json.dumps(event.payload),
                now,
            ),
        )
        await db.commit()

        notification = {
            "id": notif_id,
            "user_id": event.user_id,
            "type": event.event_type,
            "category": category.value,
            "title": title,
            "message": message,
            "priority": priority.value,
            "status": "unread",
            "metadata": json.dumps(event.payload),
            "created_at": now,
        }

        channel = await deliver(event.user_id, notification)
        logger.info("Notification %s delivered via %s for user=%s", notif_id, channel, event.user_id)

        return notification
    finally:
        await db.close()


async def get_user_notifications(
    user_id: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    db = await get_db()
    try:
        if status_filter:
            count_cursor = await db.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND status = ?",
                (user_id, status_filter),
            )
            cursor = await db.execute(
                """SELECT * FROM notifications
                   WHERE user_id = ? AND status = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_id, status_filter, limit, offset),
            )
        else:
            count_cursor = await db.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE user_id = ?",
                (user_id,),
            )
            cursor = await db.execute(
                """SELECT * FROM notifications
                   WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            )

        total = (await count_cursor.fetchone())["c"]
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total
    finally:
        await db.close()


async def get_unread_count(user_id: str) -> dict[str, int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT category, COUNT(*) as c FROM notifications
               WHERE user_id = ? AND status = 'unread'
               GROUP BY category""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        by_cat = {r["category"]: r["c"] for r in rows}
        total = sum(by_cat.values())
        return {"total": total, "by_category": by_cat}
    finally:
        await db.close()


async def mark_read(user_id: str, notification_ids: list[str]) -> int:
    db = await get_db()
    try:
        placeholders = ",".join("?" for _ in notification_ids)
        await db.execute(
            f"UPDATE notifications SET status = 'read' WHERE user_id = ? AND id IN ({placeholders})",
            [user_id, *notification_ids],
        )
        await db.commit()
        return db.total_changes
    finally:
        await db.close()


async def mark_all_read(user_id: str) -> int:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE notifications SET status = 'read' WHERE user_id = ? AND status = 'unread'",
            (user_id,),
        )
        await db.commit()
        return db.total_changes
    finally:
        await db.close()


async def get_preferences(user_id: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return {
            "user_id": user_id,
            "follow_notifications": 1,
            "faq_notifications": 1,
            "viral_notifications": 1,
            "ai_evolution_notifications": 1,
            "email_enabled": 0,
            "push_enabled": 1,
        }
    finally:
        await db.close()


async def update_preferences(user_id: str, prefs: dict) -> dict:
    db = await get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO notification_preferences
               (user_id, follow_notifications, faq_notifications, viral_notifications,
                ai_evolution_notifications, email_enabled, push_enabled, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                follow_notifications = excluded.follow_notifications,
                faq_notifications = excluded.faq_notifications,
                viral_notifications = excluded.viral_notifications,
                ai_evolution_notifications = excluded.ai_evolution_notifications,
                email_enabled = excluded.email_enabled,
                push_enabled = excluded.push_enabled,
                updated_at = excluded.updated_at""",
            (
                user_id,
                int(prefs.get("follow_notifications", True)),
                int(prefs.get("faq_notifications", True)),
                int(prefs.get("viral_notifications", True)),
                int(prefs.get("ai_evolution_notifications", True)),
                int(prefs.get("email_enabled", False)),
                int(prefs.get("push_enabled", True)),
                now,
            ),
        )
        await db.commit()
        return await get_preferences(user_id)
    finally:
        await db.close()
