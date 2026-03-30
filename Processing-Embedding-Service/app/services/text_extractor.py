from __future__ import annotations

import logging
from pathlib import Path

from app.models.enums import FileCategory
from app.utils.exceptions import TextExtractionError

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extracts raw text from various file types."""

    async def extract(self, file_path: Path, category: FileCategory, mime_type: str) -> str:
        logger.info("Extracting text from %s (category=%s)", file_path.name, category)

        extractors = {
            FileCategory.TEXT: self._extract_text,
            FileCategory.PDF: self._extract_pdf,
            FileCategory.DOCUMENT: self._extract_docx,
            FileCategory.AUDIO: self._extract_audio,
            FileCategory.VIDEO: self._extract_video,
        }

        extractor = extractors.get(category)
        if extractor is None:
            raise TextExtractionError(f"Unsupported file category: {category}")

        try:
            text = await extractor(file_path, mime_type)
            logger.info("Extracted %d characters from %s", len(text), file_path.name)
            return text
        except TextExtractionError:
            raise
        except Exception as exc:
            raise TextExtractionError(
                f"Failed to extract text from {file_path.name}: {exc}"
            ) from exc

    async def _extract_text(self, file_path: Path, _mime_type: str) -> str:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return file_path.read_text(encoding=encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        raise TextExtractionError(f"Could not decode {file_path.name} with any known encoding")

    async def _extract_pdf(self, file_path: Path, _mime_type: str) -> str:
        try:
            import pdfplumber
        except ImportError as exc:
            raise TextExtractionError("pdfplumber is required for PDF extraction") from exc

        pages_text: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                else:
                    logger.debug("Page %d of %s yielded no text", i + 1, file_path.name)

        if not pages_text:
            raise TextExtractionError(f"No extractable text found in PDF: {file_path.name}")

        return "\n\n".join(pages_text)

    async def _extract_docx(self, file_path: Path, _mime_type: str) -> str:
        try:
            from docx import Document
        except ImportError as exc:
            raise TextExtractionError("python-docx is required for DOCX extraction") from exc

        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        if not paragraphs:
            raise TextExtractionError(f"No extractable text in DOCX: {file_path.name}")

        return "\n\n".join(paragraphs)

    async def _extract_audio(self, file_path: Path, _mime_type: str) -> str:
        """Transcribe audio using OpenAI Whisper (local model)."""
        try:
            import whisper
        except ImportError as exc:
            raise TextExtractionError(
                "openai-whisper is required for audio transcription"
            ) from exc

        logger.info("Transcribing audio: %s", file_path.name)
        model = whisper.load_model("base")
        result = model.transcribe(str(file_path))
        text = result.get("text", "")

        if not text.strip():
            raise TextExtractionError(f"No speech detected in audio: {file_path.name}")

        return text

    async def _extract_video(self, file_path: Path, mime_type: str) -> str:
        """Extract audio track from video, then transcribe."""
        import subprocess
        import tempfile

        audio_path = Path(tempfile.mktemp(suffix=".wav", prefix="pes_audio_"))
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-i", str(file_path),
                    "-vn", "-acodec", "pcm_s16le",
                    "-ar", "16000", "-ac", "1",
                    str(audio_path), "-y",
                ],
                capture_output=True,
                timeout=300,
            )
            if proc.returncode != 0:
                stderr = proc.stderr.decode(errors="replace")
                raise TextExtractionError(f"ffmpeg failed: {stderr[:500]}")

            return await self._extract_audio(audio_path, mime_type)
        finally:
            audio_path.unlink(missing_ok=True)
