from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_token, encrypt_token
from app.integrations.base_client import BasePlatformClient
from app.integrations.registry import get_platform_client
from app.models.schemas import NormalizedContent
from app.models.social_account import SocialAccount
from app.models.social_content import SocialContent
from app.services.normalization_service import extract_topics

logger = logging.getLogger(__name__)


async def connect_account(
    db: AsyncSession,
    user_id: str,
    platform: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    platform_user_id: Optional[str] = None,
    platform_username: Optional[str] = None,
    scopes: Optional[str] = None,
) -> SocialAccount:
    result = await db.execute(
        select(SocialAccount).where(
            and_(SocialAccount.user_id == user_id, SocialAccount.platform == platform)
        )
    )
    account = result.scalar_one_or_none()

    if account:
        account.access_token_encrypted = encrypt_token(access_token)
        account.refresh_token_encrypted = encrypt_token(refresh_token) if refresh_token else None
        account.platform_user_id = platform_user_id or account.platform_user_id
        account.platform_username = platform_username or account.platform_username
        account.scopes = scopes
        account.is_active = 1
        account.connected_at = datetime.now(timezone.utc)
    else:
        account = SocialAccount(
            user_id=user_id,
            platform=platform,
            platform_user_id=platform_user_id,
            platform_username=platform_username,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
            scopes=scopes,
        )
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return account


async def disconnect_account(
    db: AsyncSession, user_id: str, platform: str
) -> bool:
    result = await db.execute(
        select(SocialAccount).where(
            and_(SocialAccount.user_id == user_id, SocialAccount.platform == platform)
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        return False

    account.is_active = 0
    account.access_token_encrypted = None
    account.refresh_token_encrypted = None
    await db.commit()
    return True


async def delete_user_data(
    db: AsyncSession, user_id: str, platform: str
) -> int:
    count_q = await db.execute(
        select(func.count()).select_from(SocialContent).where(
            and_(SocialContent.user_id == user_id, SocialContent.platform == platform)
        )
    )
    count = count_q.scalar() or 0

    await db.execute(
        delete(SocialContent).where(
            and_(SocialContent.user_id == user_id, SocialContent.platform == platform)
        )
    )
    await db.execute(
        delete(SocialAccount).where(
            and_(SocialAccount.user_id == user_id, SocialAccount.platform == platform)
        )
    )
    await db.commit()
    return count


async def get_user_accounts(
    db: AsyncSession, user_id: str
) -> List[SocialAccount]:
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.user_id == user_id)
    )
    return list(result.scalars().all())


async def sync_platform(
    db: AsyncSession,
    user_id: str,
    platform: str,
    max_items: int = 200,
) -> int:
    result = await db.execute(
        select(SocialAccount).where(
            and_(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.is_active == 1,
            )
        )
    )
    account = result.scalar_one_or_none()
    if not account or not account.access_token_encrypted:
        raise ValueError(f"No active {platform} account found")

    access_token = decrypt_token(account.access_token_encrypted)
    client = get_platform_client(platform)

    since = account.last_sync_at.isoformat() if account.last_sync_at else None
    items = await client.fetch_user_content(
        access_token=access_token,
        user_id=user_id,
        max_items=max_items,
        since=since,
    )

    new_count = 0
    for item in items:
        topics = extract_topics(item.content)
        item.topics = topics

        existing = await db.execute(
            select(SocialContent.id).where(
                and_(
                    SocialContent.user_id == user_id,
                    SocialContent.platform == platform,
                    SocialContent.content_text == item.content,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        content = SocialContent(
            user_id=user_id,
            platform=platform,
            content_type=item.type,
            content_text=item.content,
            topics=json.dumps(topics),
            hashtags=json.dumps(item.hashtags),
            mentions=json.dumps(item.mentions),
            engagement_score=item.engagement_score,
            content_created_at=None,
        )
        db.add(content)
        new_count += 1

    account.last_sync_at = datetime.now(timezone.utc)
    account.items_ingested = (account.items_ingested or 0) + new_count
    await db.commit()

    logger.info(
        "Synced %d new items from %s for user %s", new_count, platform, user_id
    )
    return new_count


async def get_ingestion_stats(db: AsyncSession, user_id: str) -> dict:
    total_q = await db.execute(
        select(func.count()).select_from(SocialContent).where(
            SocialContent.user_id == user_id
        )
    )
    total = total_q.scalar() or 0

    by_platform_q = await db.execute(
        select(SocialContent.platform, func.count())
        .where(SocialContent.user_id == user_id)
        .group_by(SocialContent.platform)
    )
    by_platform = dict(by_platform_q.all())

    by_type_q = await db.execute(
        select(SocialContent.content_type, func.count())
        .where(SocialContent.user_id == user_id)
        .group_by(SocialContent.content_type)
    )
    by_type = dict(by_type_q.all())

    return {
        "total_items": total,
        "by_platform": by_platform,
        "by_type": by_type,
    }
