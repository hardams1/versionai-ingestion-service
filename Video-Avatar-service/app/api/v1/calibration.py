from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies import get_face_calibration_service, verify_api_key
from app.models.enums import FaceScanStatus
from app.models.schemas import (
    CalibrationSequenceResponse,
    CalibrationStatusResponse,
    CalibrationUploadResponse,
)
from app.services.face_calibration import FaceCalibrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calibration", tags=["face-calibration"])


@router.get(
    "/sequence",
    response_model=CalibrationSequenceResponse,
    summary="Get the guided calibration prompt sequence",
)
async def get_calibration_sequence(
    calibration_svc: FaceCalibrationService = Depends(get_face_calibration_service),
    _auth: None = Depends(verify_api_key),
) -> CalibrationSequenceResponse:
    data = calibration_svc.get_calibration_sequence()
    return CalibrationSequenceResponse(**data)


@router.post(
    "/{user_id}/upload",
    response_model=CalibrationUploadResponse,
    summary="Upload a face calibration video",
    description=(
        "Upload a webcam-recorded calibration video (WebM or MP4). "
        "The video should contain guided head movements, expressions, and speech "
        "for 3D face reconstruction and lip-sync calibration."
    ),
)
async def upload_calibration_video(
    user_id: str,
    video: UploadFile = File(..., description="Calibration video (WebM or MP4)"),
    calibration_svc: FaceCalibrationService = Depends(get_face_calibration_service),
    _auth: None = Depends(verify_api_key),
) -> CalibrationUploadResponse:
    video_data = await video.read()
    content_type = video.content_type or "video/webm"

    logger.info(
        "Calibration upload: user=%s, size=%d, type=%s",
        user_id, len(video_data), content_type,
    )

    video_path, status = await calibration_svc.upload_calibration_video(
        user_id=user_id,
        video_data=video_data,
        content_type=content_type,
    )

    return CalibrationUploadResponse(
        user_id=user_id,
        video_path=video_path,
        face_scan_status=status,
        message="Calibration video uploaded. Face reconstruction is processing in the background.",
    )


@router.get(
    "/{user_id}/status",
    response_model=CalibrationStatusResponse,
    summary="Check face calibration status for a user",
)
async def get_calibration_status(
    user_id: str,
    calibration_svc: FaceCalibrationService = Depends(get_face_calibration_service),
    _auth: None = Depends(verify_api_key),
) -> CalibrationStatusResponse:
    data = await calibration_svc.get_calibration_status(user_id)
    return CalibrationStatusResponse(**data)


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Delete face calibration data for a user",
)
async def delete_calibration(
    user_id: str,
    calibration_svc: FaceCalibrationService = Depends(get_face_calibration_service),
    _auth: None = Depends(verify_api_key),
) -> None:
    await calibration_svc.delete_calibration(user_id)
