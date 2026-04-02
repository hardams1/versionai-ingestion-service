from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services.auth_service import get_current_user, login, signup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup_endpoint(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    user = await signup(body.username, body.password, body.email, db)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        onboarding_completed=user.onboarding_completed,
    )


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, token = await login(body.username, body.password, db)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        onboarding_completed=user.onboarding_completed,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        onboarding_completed=user.onboarding_completed,
    )
