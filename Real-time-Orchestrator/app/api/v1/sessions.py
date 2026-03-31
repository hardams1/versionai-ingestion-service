from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_session_manager, verify_api_key
from app.services.session import SessionManager

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "",
    summary="List active WebSocket sessions",
)
async def list_sessions(
    session_mgr: SessionManager = Depends(get_session_manager),
    _auth: None = Depends(verify_api_key),
) -> dict:
    return {"active_sessions": session_mgr.active_count}
