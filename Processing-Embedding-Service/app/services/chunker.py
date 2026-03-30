from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.schemas import TextChunk

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_PARAGRAPH_SEPARATORS = ["\n\n\n", "\n\n", "\n", ". ", " "]


class TextChunker:
    """
    Recursive character text splitter with token-aware sizing.
    Uses tiktoken for accurate token counts with OpenAI models.
    """

    def __init__(self, settings: Settings) -> None:
        self._chunk_size = settings.chunk_size
        self._chunk_overlap = settings.chunk_overlap
        self._encoder = self._get_encoder(settings.openai_embedding_model)

    @staticmethod
    def _get_encoder(model_name: str):
        try:
            import tiktoken
            return tiktoken.encoding_for_model(model_name)
        except Exception:
            import tiktoken
            return tiktoken.get_encoding("cl100k_base")

    def _token_count(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def chunk(self, text: str, metadata: dict | None = None) -> list[TextChunk]:
        if not text.strip():
            return []

        raw_chunks = self._split_recursive(text, _PARAGRAPH_SEPARATORS)
        merged = self._merge_with_overlap(raw_chunks)

        chunks: list[TextChunk] = []
        char_offset = 0

        for i, chunk_text in enumerate(merged):
            start = text.find(chunk_text, char_offset)
            if start == -1:
                start = char_offset
            end = start + len(chunk_text)

            chunk_meta = dict(metadata) if metadata else {}
            chunk_meta["chunk_index"] = i

            chunks.append(TextChunk(
                chunk_index=i,
                text=chunk_text,
                token_count=self._token_count(chunk_text),
                start_char=start,
                end_char=end,
                metadata=chunk_meta,
            ))
            char_offset = start + 1

        logger.info("Split text into %d chunks (target=%d tokens)", len(chunks), self._chunk_size)
        return chunks

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if self._token_count(text) <= self._chunk_size:
            return [text.strip()] if text.strip() else []

        if not separators:
            return self._split_by_tokens(text)

        sep = separators[0]
        remaining_seps = separators[1:]

        parts = text.split(sep)
        results: list[str] = []
        current = ""

        for part in parts:
            candidate = f"{current}{sep}{part}" if current else part
            if self._token_count(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    results.extend(self._split_recursive(current.strip(), remaining_seps))
                current = part

        if current.strip():
            results.extend(self._split_recursive(current.strip(), remaining_seps))

        return results

    def _split_by_tokens(self, text: str) -> list[str]:
        """Last-resort: split by token boundaries."""
        tokens = self._encoder.encode(text)
        chunks: list[str] = []
        for i in range(0, len(tokens), self._chunk_size):
            chunk_tokens = tokens[i : i + self._chunk_size]
            chunks.append(self._encoder.decode(chunk_tokens))
        return chunks

    def _merge_with_overlap(self, chunks: list[str]) -> list[str]:
        if not chunks or self._chunk_overlap <= 0:
            return chunks

        merged: list[str] = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                merged.append(chunk)
                continue

            prev_tokens = self._encoder.encode(chunks[i - 1])
            overlap_tokens = prev_tokens[-self._chunk_overlap :] if len(prev_tokens) > self._chunk_overlap else prev_tokens
            overlap_text = self._encoder.decode(overlap_tokens)

            combined = f"{overlap_text} {chunk}".strip()
            if self._token_count(combined) > self._chunk_size * 1.5:
                merged.append(chunk)
            else:
                merged.append(combined)

        return merged
