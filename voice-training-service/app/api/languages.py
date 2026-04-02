from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.models.schemas import (
    SUPPORTED_LANGUAGES,
    DetectLanguageRequest,
    DetectLanguageResponse,
    TranslateRequest,
    TranslateResponse,
)
from app.services.language_service import LanguageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/language", tags=["language"])


@router.get("/supported")
async def list_supported():
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/detect", response_model=DetectLanguageResponse)
async def detect_language(
    body: DetectLanguageRequest,
    settings: Settings = Depends(get_settings),
):
    svc = LanguageService(settings)
    code, confidence = svc.detect(body.text)
    return DetectLanguageResponse(
        detected_language=code,
        language_name=SUPPORTED_LANGUAGES.get(code, code),
        confidence=round(confidence, 3),
    )


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    body: TranslateRequest,
    settings: Settings = Depends(get_settings),
):
    svc = LanguageService(settings)

    src = body.source_language
    if not src:
        src, _ = svc.detect(body.text)

    translated = await svc.translate(body.text, src, body.target_language)

    return TranslateResponse(
        original_text=body.text,
        translated_text=translated,
        source_language=src,
        target_language=body.target_language,
    )
