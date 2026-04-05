from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.integrations.registry import SUPPORTED_PLATFORMS, get_platform_client
from app.models.schemas import (
    AccountStatusResponse,
    AllAccountsResponse,
    DeleteDataResponse,
    DisconnectResponse,
)
from app.services.ingestion_service import (
    delete_user_data,
    disconnect_account,
    get_user_accounts,
)

router = APIRouter(prefix="/connect", tags=["connections"])


@router.get("/platforms")
async def list_platforms():
    """List all supported social media platforms and whether real OAuth is configured."""
    items = []
    for p in SUPPORTED_PLATFORMS:
        client = get_platform_client(p)
        has_keys = client.has_oauth_keys()
        items.append({
            "platform": p,
            "configured": has_keys,
            "oauth_available": has_keys,
            "auth_mode": "live" if has_keys else "development",
        })
    return {"platforms": items}


@router.get("/accounts", response_model=AllAccountsResponse)
async def list_accounts(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected social accounts for the current user."""
    accounts = await get_user_accounts(db, user["user_id"])
    active_map = {a.platform: a for a in accounts if a.is_active}

    items = []
    for p in SUPPORTED_PLATFORMS:
        account = active_map.get(p)
        items.append(AccountStatusResponse(
            platform=p,
            is_connected=account is not None,
            platform_username=account.platform_username if account else None,
            connected_at=account.connected_at.isoformat() if account and account.connected_at else None,
            last_sync_at=account.last_sync_at.isoformat() if account and account.last_sync_at else None,
            items_ingested=account.items_ingested if account else 0,
        ))

    return AllAccountsResponse(accounts=items)


@router.post("/disconnect/{platform}", response_model=DisconnectResponse)
async def disconnect(
    platform: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a social account (tokens are wiped)."""
    success = await disconnect_account(db, user["user_id"], platform)
    if not success:
        raise HTTPException(status_code=404, detail=f"No {platform} account found")

    return DisconnectResponse(
        platform=platform,
        status="disconnected",
        message=f"{platform.title()} account disconnected. Tokens have been removed.",
    )


@router.delete("/data/{platform}", response_model=DeleteDataResponse)
async def delete_data(
    platform: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all ingested data for a platform (GDPR compliance)."""
    count = await delete_user_data(db, user["user_id"], platform)
    return DeleteDataResponse(
        platform=platform,
        items_deleted=count,
        status="deleted",
    )
