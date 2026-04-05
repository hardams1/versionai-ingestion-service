from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.core.security import get_current_user
from app.db import (
    delete_record,
    get_db,
    get_record,
    get_records_by_user,
    get_summary_by_user,
    insert_record,
)
from app.dependencies import get_storage_service, verify_api_key
from app.services.storage import BaseStorageService
from app.services.thumbnail import generate_text_preview, generate_thumbnail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])

EXTENSION_MIMES = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".webm": "video/webm", ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/mp4",
    ".txt": "text/plain", ".csv": "text/csv", ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
}

KEY_PATTERN = re.compile(
    r"^uploads/(?P<category>\w+)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<uid>[0-9a-f]+)_(?P<filename>.+)$"
)


# ---------------------------------------------------------------------------
# Seed / migrate existing files into the DB for a user
# ---------------------------------------------------------------------------

async def seed_existing_files(user_id: str, settings: Settings) -> int:
    """Scan local storage and insert any files not yet in the DB for this user."""
    root = Path(settings.local_storage_path)
    uploads_dir = root / "uploads"
    if not uploads_dir.exists():
        return 0

    db = await get_db()
    count = 0
    try:
        for cat_dir in sorted(uploads_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name

            for file_path in cat_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                rel_key = str(file_path.relative_to(root))
                m = KEY_PATTERN.match(rel_key)

                if m:
                    original_name = m.group("filename")
                    upload_date = f"{m.group('year')}-{m.group('month')}-{m.group('day')}"
                else:
                    original_name = file_path.name
                    upload_date = datetime.fromtimestamp(
                        file_path.stat().st_mtime, tz=timezone.utc
                    ).strftime("%Y-%m-%d")

                stat = file_path.stat()
                ext = file_path.suffix.lower()
                mime = EXTENSION_MIMES.get(ext, "application/octet-stream")

                thumb_path: str | None = None
                if category == "video":
                    thumb_path = await generate_thumbnail(str(file_path), rel_key)

                ingestion_id = str(uuid.uuid4())
                await insert_record(
                    db,
                    ingestion_id=ingestion_id,
                    user_id=user_id,
                    filename=original_name,
                    category=category,
                    s3_key=rel_key,
                    size_bytes=stat.st_size,
                    mime_type=mime,
                    thumbnail_path=thumb_path,
                )
                count += 1
        logger.info("Seeded %d existing files for user %s", count, user_id)
    finally:
        await db.close()
    return count


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List authenticated user's content, optionally filtered by category",
)
async def list_content(
    category: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    user_id = current_user["user_id"]
    db = await get_db()
    try:
        records = await get_records_by_user(db, user_id, category)

        if len(records) == 0:
            seeded = await seed_existing_files(user_id, settings)
            if seeded > 0:
                records = await get_records_by_user(db, user_id, category)
    finally:
        await db.close()

    items = []
    for r in records:
        ext = Path(r["filename"]).suffix.lower().lstrip(".")
        items.append({
            "ingestion_id": r["ingestion_id"],
            "filename": r["filename"],
            "category": r["category"],
            "size_bytes": r["size_bytes"],
            "mime_type": r["mime_type"],
            "upload_date": r["created_at"][:10] if r["created_at"] else "",
            "s3_key": r["s3_key"],
            "extension": ext,
            "has_thumbnail": bool(r.get("thumbnail_path")),
        })

    return {"items": items, "total": len(items)}


@router.get(
    "/summary",
    summary="Get authenticated user's content summary grouped by category",
)
async def content_summary(
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    user_id = current_user["user_id"]
    db = await get_db()
    try:
        summary_rows = await get_summary_by_user(db, user_id)

        if not summary_rows:
            seeded = await seed_existing_files(user_id, settings)
            if seeded > 0:
                summary_rows = await get_summary_by_user(db, user_id)
    finally:
        await db.close()

    categories = []
    total_files = 0
    total_bytes = 0
    for row in summary_rows:
        categories.append({
            "category": row["category"],
            "count": row["count"],
            "total_size_bytes": row["total_size_bytes"] or 0,
        })
        total_files += row["count"]
        total_bytes += row["total_size_bytes"] or 0

    return {
        "categories": categories,
        "total_files": total_files,
        "total_size_bytes": total_bytes,
    }


@router.get(
    "/file/{ingestion_id}",
    summary="Serve the original file for preview/download",
)
async def serve_file(
    ingestion_id: str,
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    db = await get_db()
    try:
        record = await get_record(db, ingestion_id)
    finally:
        await db.close()

    if not record or record["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(settings.local_storage_path) / record["s3_key"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type=record["mime_type"],
        filename=record["filename"],
    )


@router.get(
    "/thumbnail/{ingestion_id}",
    summary="Serve video thumbnail image",
)
async def serve_thumbnail(
    ingestion_id: str,
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    db = await get_db()
    try:
        record = await get_record(db, ingestion_id)
    finally:
        await db.close()

    if not record or record["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")

    if record.get("thumbnail_path") and Path(record["thumbnail_path"]).exists():
        return FileResponse(path=record["thumbnail_path"], media_type="image/jpeg")

    storage_root = Path(settings.local_storage_path)
    source = storage_root / record["s3_key"]
    thumb = await generate_thumbnail(str(source), record["s3_key"])
    if thumb and Path(thumb).exists():
        db2 = await get_db()
        try:
            await db2.execute(
                "UPDATE upload_records SET thumbnail_path = ? WHERE ingestion_id = ?",
                (thumb, ingestion_id),
            )
            await db2.commit()
        finally:
            await db2.close()
        return FileResponse(path=thumb, media_type="image/jpeg")

    raise HTTPException(status_code=404, detail="Thumbnail not available")


@router.get(
    "/preview/{ingestion_id}",
    summary="Get a text preview of text/pdf/document files",
)
async def text_preview(
    ingestion_id: str,
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    db = await get_db()
    try:
        record = await get_record(db, ingestion_id)
    finally:
        await db.close()

    if not record or record["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Not found")

    file_path = Path(settings.local_storage_path) / record["s3_key"]
    preview = await generate_text_preview(str(file_path))

    return {
        "ingestion_id": ingestion_id,
        "filename": record["filename"],
        "preview_text": preview or "(Unable to generate preview)",
    }


@router.delete(
    "/{ingestion_id}",
    summary="Delete a content item (owner only)",
)
async def delete_content(
    ingestion_id: str,
    current_user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    storage: BaseStorageService = Depends(get_storage_service),
) -> dict:
    db = await get_db()
    try:
        record = await get_record(db, ingestion_id)
        if not record or record["user_id"] != current_user["user_id"]:
            raise HTTPException(status_code=404, detail="File not found")

        await storage.delete(record["s3_key"])

        if record.get("thumbnail_path"):
            thumb = Path(record["thumbnail_path"])
            thumb.unlink(missing_ok=True)

        await delete_record(db, ingestion_id)
    finally:
        await db.close()

    logger.info("User %s deleted content %s (%s)", current_user["user_id"], ingestion_id, record["filename"])
    return {"detail": "Deleted", "ingestion_id": ingestion_id, "filename": record["filename"]}
