from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TextChunk:
    """Один фрагмент документа."""
    content: str
    index: int
    meta: dict = field(default_factory=dict)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")


class RecursiveChunker:
    """
    Рекурсивный сплиттер с перекрытием.
    Порядок разделителей: абзац → предложение → слово → жёсткий разрез.
    """

    def __init__(
            self,
            chunk_size: int = 800,
            chunk_overlap: int = 120,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str, base_meta: dict | None = None) -> list[TextChunk]:
        text = self._normalize(text)
        if not text:
            return []

        raw_parts = self._split_to_size(text)
        chunks: list[TextChunk] = []
        for idx, part in enumerate(raw_parts):
            part = part.strip()
            if not part:
                continue
            chunks.append(
                TextChunk(
                    content=part,
                    index=idx,
                    meta={**(base_meta or {}), "char_len": len(part)},
                )
            )
        return self._apply_overlap(chunks)

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return re.sub(r"[ \t]+", " ", text).strip()

    def _split_to_size(self, text: str) -> list[str]:
        """Рекурсивно режет текст, пока куски не станут <= chunk_size."""
        if len(text) <= self.chunk_size:
            return [text]

        for splitter in (
                lambda t: _PARAGRAPH_SPLIT.split(t),
                lambda t: _SENTENCE_SPLIT.split(t),
                lambda t: t.split(" "),
        ):
            parts = [p for p in splitter(text) if p and p.strip()]
            if len(parts) > 1:
                result: list[str] = []
                for part in parts:
                    result.extend(self._split_to_size(part))
                return result

        # fallback: жёсткий разрез
        return [
            text[i: i + self.chunk_size]
            for i in range(0, len(text), self.chunk_size)
        ]

    def _apply_overlap(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Добавляет хвост предыдущего чанка в начало следующего."""
        if not chunks or self.chunk_overlap == 0:
            return chunks

        result: list[TextChunk] = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            tail = prev.content[-self.chunk_overlap:]
            merged = f"{tail}\n{cur.content}"
            result.append(
                TextChunk(
                    content=merged,
                    index=cur.index,
                    meta={**cur.meta, "overlap_chars": len(tail)},
                )
            )
        return result
