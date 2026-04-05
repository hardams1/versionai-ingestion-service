from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.integrations.registry import SUPPORTED_PLATFORMS, get_platform_client
from app.models.schemas import (
    AccountStatusResponse,
    AllAccountsResponse,
    ConnectRequest,
    ConnectResponse,
    DeleteDataResponse,
    DisconnectResponse,
    OAuthCallbackRequest,
    OAuthInitResponse,
)
from app.services.ingestion_service import (
    connect_account,
    delete_user_data,
    disconnect_account,
    get_user_accounts,
)

router = APIRouter(prefix="/connect", tags=["connections"])


@router.get("/platforms")
async def list_platforms():
    """List all supported social media platforms."""
    settings = get_settings()
    platforms = []
    for p in SUPPORTED_PLATFORMS:
        configured = False
        if p == "twitter" and settings.twitter_client_id:
            configured = True
        elif p == "facebook" and settings.facebook_app_id:
            configured = True
        elif p == "instagram" and settings.instagram_app_id:
            configured = True
        elif p == "tiktok" and settings.tiktok_client_key:
            configured = True
        elif p == "snapchat":
            configured = False

        platforms.append({
            "platform": p,
            "configured": configured,
            "oauth_available": configured,
        })
    return {"platforms": platforms}


@router.get("/oauth/{platform}", response_model=OAuthInitResponse)
async def init_oauth(
    platform: str,
    user: dict = Depends(get_current_user),
):
    """Generate an OAuth authorization URL for the given platform."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    settings = get_settings()
    state = secrets.token_urlsafe(32)
    redirect_uri = f"{settings.oauth_redirect_base_url}/{platform}"

    client = get_platform_client(platform)
    url = client.get_oauth_url(state, redirect_uri)

    if not url:
        raise HTTPException(
            status_code=501,
            detail=f"OAuth not yet available for {platform}",
        )

    return OAuthInitResponse(authorization_url=url, state=state)


@router.post("/oauth/callback", response_model=ConnectResponse)
async def oauth_callback(
    req: OAuthCallbackRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange OAuth code for tokens and connect the account."""
    settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base_url}/{req.platform}"

    client = get_platform_client(req.platform)
    token_data = await client.exchange_code(req.code, redirect_uri)

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token")

    account = await connect_account(
        db=db,
        user_id=user["user_id"],
        platform=req.platform,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    return ConnectResponse(
        id=account.id,
        platform=account.platform,
        platform_username=account.platform_username,
        status="connected",
        connected_at=account.connected_at.isoformat() if account.connected_at else "",
    )


@router.post("/{platform}", response_model=ConnectResponse)
async def connect_direct(
    platform: str,
    req: ConnectRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a social account using a directly provided access token."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    account = await connect_account(
        db=db,
        user_id=user["user_id"],
        platform=platform,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        platform_user_id=req.platform_user_id,
        platform_username=req.platform_username,
        scopes=req.scopes,
    )

    return ConnectResponse(
        id=account.id,
        platform=account.platform,
        platform_username=account.platform_username,
        status="connected",
        connected_at=account.connected_at.isoformat() if account.connected_at else "",
    )


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
