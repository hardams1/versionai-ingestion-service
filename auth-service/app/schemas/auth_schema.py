from __future__ import annotations

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    onboarding_completed: bool


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    is_active: bool
    onboarding_completed: bool
