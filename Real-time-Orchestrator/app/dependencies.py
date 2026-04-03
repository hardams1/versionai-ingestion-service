from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.brain_client import BrainClient
from app.services.pipeline import OrchestrationPipeline
from app.services.session import SessionManager
from app.services.settings_client import SettingsClient
from app.services.social_client import SocialGraphClient
from app.services.stt_client import STTClient
from app.services.video_client import VideoClient
from app.services.voice_client import VoiceClient
from app.services.voice_training_client import VoiceTrainingClient
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
def get_settings_client() -> SettingsClient:
    return SettingsClient(get_settings())


@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager(max_sessions=get_settings().max_concurrent_sessions)


@lru_cache
def get_voice_training_client() -> VoiceTrainingClient:
    return VoiceTrainingClient(get_settings())


@lru_cache
def get_stt_client() -> STTClient:
    return STTClient(get_settings())


@lru_cache
def get_social_client() -> SocialGraphClient:
    return SocialGraphClient(get_settings())


@lru_cache
def get_pipeline() -> OrchestrationPipeline:
    return OrchestrationPipeline(
        brain=get_brain_client(),
        voice=get_voice_client(),
        video=get_video_client(),
        settings_client=get_settings_client(),
        voice_training_client=get_voice_training_client(),
        stt_client=get_stt_client(),
        social_client=get_social_client(),
    )


@lru_cache
def get_ws_handler() -> WebSocketHandler:
    return WebSocketHandler(
        pipeline=get_pipeline(),
        session_mgr=get_session_manager(),
        settings=get_settings(),
    )
