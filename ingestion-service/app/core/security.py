from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def decode_token(token: str, settings: Settings) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError:
        logger.info("Token expired")
        return None
    except JWTError:
        logger.warning("Token decode error")
        return None


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    _token: Optional[str] = Query(default=None, alias="_token"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Extract user from Bearer header or _token query param (for <img>/<video> tags)."""
    raw_token: str | None = None
    if creds:
        raw_token = creds.credentials
    elif _token:
        raw_token = _token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(raw_token, settings)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": payload["sub"], "username": payload.get("username", "")}


async def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Optional[dict]:
    """Same as get_current_user but returns None instead of raising on missing/invalid token."""
    if not creds:
        return None
    payload = decode_token(creds.credentials, settings)
    if not payload or "sub" not in payload:
        return None
    return {"user_id": payload["sub"], "username": payload.get("username", "")}
