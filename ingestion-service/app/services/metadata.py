from __future__ import annotations

import logging
from pathlib import PurePosixPath

from app.models.enums import (
    CATEGORY_TO_PIPELINES,
    FileCategory,
    ProcessingPipeline,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Extracts metadata and determines downstream processing pipelines."""

    @staticmethod
    def resolve_pipelines(category: FileCategory) -> list[ProcessingPipeline]:
        pipelines = CATEGORY_TO_PIPELINES.get(category, [])
        logger.debug("Resolved pipelines for %s: %s", category, pipelines)
        return pipelines

    @staticmethod
    def build_metadata(
        filename: str,
        mime_type: str,
        category: FileCategory,
        size_bytes: int,
        checksum: str,
    ) -> dict:
        ext = PurePosixPath(filename).suffix.lower()
        return {
            "original_filename": filename,
            "extension": ext,
            "mime_type": mime_type,
            "category": category.value,
            "size_bytes": size_bytes,
            "checksum_sha256": checksum,
        }
