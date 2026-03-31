from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.brain_client import BrainClient
from app.services.pipeline import OrchestrationPipeline
from app.services.session import SessionManager
from app.services.video_client import VideoClient
from app.services.voice_client import VoiceClient
from app.ws.handler import WebSocketHandler

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    settings: Settings = Depends(get_settings),
    api_key: str | None = Security(api_key_header),
) -> None:
    if settings.api_key is None:
        return
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


@lru_cache
def get_brain_client() -> BrainClient:
    return BrainClient(get_settings())


@lru_cache
def get_voice_client() -> VoiceClient:
    return VoiceClient(get_settings())


@lru_cache
def get_video_client() -> VideoClient:
    return VideoClient(get_settings())


@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager(max_sessions=get_settings().max_concurrent_sessions)


@lru_cache
def get_pipeline() -> OrchestrationPipeline:
    return OrchestrationPipeline(
        brain=get_brain_client(),
        voice=get_voice_client(),
        video=get_video_client(),
    )


@lru_cache
def get_ws_handler() -> WebSocketHandler:
    return WebSocketHandler(
        pipeline=get_pipeline(),
        session_mgr=get_session_manager(),
        settings=get_settings(),
    )
