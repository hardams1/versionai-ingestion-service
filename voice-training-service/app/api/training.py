from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.voice_profile import VoiceTrainingProfile
from app.models.schemas import (
    CloneVoiceRequest,
    CloneVoiceResponse,
    UpdateLanguageRequest,
    VoiceProfileResponse,
    VoiceSampleResponse,
)
from app.services.audio_processing import AudioProcessor
from app.services.feature_extraction import FeatureExtractor
from app.services.training_scripts import get_training_script
from app.services.voice_cloner import VoiceCloner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice-training"])

audio_processor = AudioProcessor()
feature_extractor = FeatureExtractor()


@router.get("/training-script")
async def training_script(language: str = Query(default="en")):
    return get_training_script(language)


@router.post("/upload-sample", response_model=VoiceSampleResponse)
async def upload_sample(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    if len(data) > settings.max_audio_file_size:
        raise HTTPException(400, f"File too large (max {settings.max_audio_file_size // (1024 * 1024)}MB)")

    ct = file.content_type or "audio/mpeg"
    try:
        duration, _ = audio_processor.validate_audio(data, ct)
    except ValueError as e:
        raise HTTPException(400, str(e))

    mp3_data = audio_processor.convert_to_mp3(data, ct)

    samples_dir = Path(settings.audio_samples_dir) / user_id
    samples_dir.mkdir(parents=True, exist_ok=True)
    sample_id = str(uuid.uuid4())[:8]
    sample_path = samples_dir / f"{sample_id}.mp3"
    sample_path.write_bytes(mp3_data)

    features = feature_extractor.extract(mp3_data)

    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = VoiceTrainingProfile(
            user_id=user_id,
            total_samples=0,
            total_duration_seconds=0.0,
            cloning_status="pending",
            primary_language="en",
            voice_service_synced=False,
        )
        db.add(profile)

    profile.total_samples = (profile.total_samples or 0) + 1
    profile.total_duration_seconds = (profile.total_duration_seconds or 0.0) + duration

    if features.get("avg_pitch_hz"):
        profile.avg_pitch_hz = features["avg_pitch_hz"]
    if features.get("speaking_rate_wpm"):
        profile.speaking_rate_wpm = features["speaking_rate_wpm"]
    if features.get("tone_profile"):
        profile.tone_profile = features["tone_profile"]

    await db.commit()

    return VoiceSampleResponse(
        sample_id=sample_id,
        duration_seconds=round(duration, 1),
        status="stored",
        message=(
            f"Sample stored ({round(duration, 1)}s). "
            f"Total: {profile.total_samples} samples, {round(profile.total_duration_seconds, 1)}s"
        ),
    )


@router.post("/clone", response_model=CloneVoiceResponse)
async def clone_voice(
    body: CloneVoiceRequest = CloneVoiceRequest(),
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile or profile.total_samples == 0:
        raise HTTPException(400, "No voice samples uploaded yet")

    if profile.total_duration_seconds < settings.min_audio_duration_seconds:
        raise HTTPException(
            400,
            f"Need at least {int(settings.min_audio_duration_seconds)}s of audio "
            f"(currently {round(profile.total_duration_seconds, 1)}s). "
            f"Read the full 2-minute training script for best results.",
        )

    cloner = VoiceCloner(settings)
    if not cloner.available:
        raise HTTPException(503, "Voice cloning not available (ElevenLabs API key not configured)")

    samples_dir = Path(settings.audio_samples_dir) / user_id
    audio_files = []
    for mp3_file in sorted(samples_dir.glob("*.mp3")):
        audio_files.append((mp3_file.name, mp3_file.read_bytes()))

    if not audio_files:
        raise HTTPException(400, "No audio sample files found on disk")

    if profile.elevenlabs_voice_id:
        await cloner.delete_voice(profile.elevenlabs_voice_id)

    voice_name = body.voice_name or f"VersionAI-{user_id[:8]}"
    voice_id = await cloner.clone_voice(audio_files, voice_name)

    if voice_id:
        profile.elevenlabs_voice_id = voice_id
        profile.voice_name = voice_name
        profile.cloning_status = "ready"

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.voice_service_url}/api/v1/profiles",
                    json={
                        "user_id": user_id,
                        "voice_id": voice_id,
                        "provider": "elevenlabs",
                        "display_name": voice_name,
                    },
                )
                if resp.status_code in (200, 201):
                    profile.voice_service_synced = True
                    logger.info("Voice profile synced to Voice Service for user=%s", user_id)
        except Exception as e:
            logger.warning("Failed to sync voice profile: %s", e)

        await db.commit()

        quality_note = ""
        if profile.total_duration_seconds < 120:
            quality_note = (
                " For even better accuracy, record the full 2-minute training script "
                "and retrain your voice."
            )

        return CloneVoiceResponse(
            user_id=user_id,
            elevenlabs_voice_id=voice_id,
            cloning_status="ready",
            message=f"Voice cloned successfully! AI will now speak in your voice.{quality_note}",
        )
    else:
        profile.cloning_status = "failed"
        await db.commit()
        raise HTTPException(502, "Voice cloning failed. Please try again with clearer audio samples.")


@router.post("/retrain", response_model=CloneVoiceResponse)
async def retrain_voice(
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Clear existing voice clone and all samples so the user can start fresh."""
    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile and profile.elevenlabs_voice_id:
        cloner = VoiceCloner(settings)
        await cloner.delete_voice(profile.elevenlabs_voice_id)

    samples_dir = Path(settings.audio_samples_dir) / user_id
    if samples_dir.exists():
        import shutil
        shutil.rmtree(samples_dir)
    samples_dir.mkdir(parents=True, exist_ok=True)

    if profile:
        profile.elevenlabs_voice_id = None
        profile.voice_name = None
        profile.cloning_status = "pending"
        profile.total_samples = 0
        profile.total_duration_seconds = 0.0
        profile.voice_service_synced = False
        profile.avg_pitch_hz = None
        profile.speaking_rate_wpm = None
        profile.tone_profile = None
    else:
        profile = VoiceTrainingProfile(
            user_id=user_id,
            total_samples=0,
            total_duration_seconds=0.0,
            cloning_status="pending",
            primary_language="en",
            voice_service_synced=False,
        )
        db.add(profile)

    await db.commit()

    return CloneVoiceResponse(
        user_id=user_id,
        elevenlabs_voice_id=None,
        cloning_status="pending",
        message=(
            "Voice profile reset. Record the full 2-minute training script "
            "in a quiet room for the best results."
        ),
    )


@router.get("/profile", response_model=VoiceProfileResponse)
async def get_profile(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return VoiceProfileResponse(
            user_id=user_id,
            cloning_status="pending",
            primary_language="en",
            total_samples=0,
            total_duration_seconds=0.0,
            voice_service_synced=False,
        )

    pref_langs: list[str] = []
    if profile.preferred_languages:
        try:
            pref_langs = json.loads(profile.preferred_languages)
        except Exception:
            pass

    return VoiceProfileResponse(
        user_id=user_id,
        elevenlabs_voice_id=profile.elevenlabs_voice_id,
        voice_name=profile.voice_name,
        cloning_status=profile.cloning_status,
        primary_language=profile.primary_language,
        preferred_languages=pref_langs,
        total_samples=profile.total_samples,
        total_duration_seconds=round(profile.total_duration_seconds, 1),
        avg_pitch_hz=profile.avg_pitch_hz,
        speaking_rate_wpm=profile.speaking_rate_wpm,
        voice_service_synced=profile.voice_service_synced,
    )


@router.get("/profile/{target_user_id}/public")
async def get_public_profile(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == target_user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {
            "user_id": target_user_id,
            "cloning_status": "pending",
            "elevenlabs_voice_id": None,
            "primary_language": "en",
        }
    return {
        "user_id": profile.user_id,
        "elevenlabs_voice_id": profile.elevenlabs_voice_id,
        "cloning_status": profile.cloning_status,
        "primary_language": profile.primary_language,
        "preferred_languages": json.loads(profile.preferred_languages) if profile.preferred_languages else [],
    }


@router.put("/language")
async def update_language(
    body: UpdateLanguageRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceTrainingProfile).where(VoiceTrainingProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = VoiceTrainingProfile(user_id=user_id)
        db.add(profile)

    profile.primary_language = body.primary_language
    profile.preferred_languages = json.dumps(body.preferred_languages)
    await db.commit()

    return {
        "status": "ok",
        "primary_language": body.primary_language,
        "preferred_languages": body.preferred_languages,
    }
