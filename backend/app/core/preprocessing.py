from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])([\t \r\f\v]*\n+|[\t ]+)(?=[\"'([{]*\w)")


@dataclass(frozen=True, slots=True)
class PreparedText:
    leading: str
    segments: tuple[str, ...]
    separators: tuple[str, ...]
    trailing: str

    def rebuild(self, corrected_segments: list[str]) -> str:
        if len(corrected_segments) != len(self.segments):
            raise ValueError("corrected segment count does not match input")
        pieces: list[str] = [self.leading]
        for index, segment in enumerate(corrected_segments):
            pieces.append(segment.strip() or self.segments[index])
            if index < len(self.separators):
                pieces.append(self.separators[index])
        pieces.append(self.trailing)
        return "".join(pieces)


class TextPreprocessor:
    """Normalizes safe Unicode forms and chunks text without grammar rules."""

    def __init__(self, max_segment_chars: int = 1_500) -> None:
        self.max_segment_chars = max_segment_chars

    def prepare(self, text: str) -> PreparedText:
        text = unicodedata.normalize("NFC", text)
        leading_length = len(text) - len(text.lstrip())
        trailing_length = len(text) - len(text.rstrip())
        leading = text[:leading_length]
        trailing = text[len(text) - trailing_length :] if trailing_length else ""
        core_end = len(text) - trailing_length if trailing_length else len(text)
        core = text[leading_length:core_end]

        raw_parts = _SENTENCE_BOUNDARY.split(core)
        sentence_parts = raw_parts[0::2]
        separators = raw_parts[1::2]
        segments: list[str] = []
        rebuilt_separators: list[str] = []

        for part_index, part in enumerate(sentence_parts):
            chunks = self._split_long_segment(part)
            for chunk_index, chunk in enumerate(chunks):
                if segments:
                    if chunk_index > 0:
                        rebuilt_separators.append(" ")
                    else:
                        rebuilt_separators.append(separators[part_index - 1])
                segments.append(chunk)

        return PreparedText(
            leading=leading,
            segments=tuple(segments or [core]),
            separators=tuple(rebuilt_separators),
            trailing=trailing,
        )

    def _split_long_segment(self, text: str) -> list[str]:
        if len(text) <= self.max_segment_chars:
            return [text]
        words = text.split()
        if not words:
            return [text]
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0
        for word in words:
            additional = len(word) + (1 if current else 0)
            if current and current_length + additional > self.max_segment_chars:
                chunks.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length += additional
        if current:
            chunks.append(" ".join(current))
        return chunks
