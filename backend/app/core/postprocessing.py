from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from backend.app.schemas import EditKind, Suggestion

_TOKEN = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class TokenSpan:
    value: str
    start: int
    end: int


def _tokens(text: str) -> list[TokenSpan]:
    return [TokenSpan(match.group(), match.start(), match.end()) for match in _TOKEN.finditer(text)]


def _slice_for_tokens(text: str, tokens: list[TokenSpan], start: int, end: int) -> str:
    if start == end:
        return ""
    return text[tokens[start].start : tokens[end - 1].end]


def _source_offsets(text: str, tokens: list[TokenSpan], start: int, end: int) -> tuple[int, int]:
    if start < end:
        return tokens[start].start, tokens[end - 1].end
    if start < len(tokens):
        return tokens[start].start, tokens[start].start
    return len(text), len(text)


class DiffPostprocessor:
    """Converts model output into span-addressable edits for the extension."""

    def suggestions(self, original: str, corrected: str, limit: int = 50) -> list[Suggestion]:
        source = _tokens(original)
        target = _tokens(corrected)
        matcher = SequenceMatcher(
            a=[token.value for token in source],
            b=[token.value for token in target],
            autojunk=False,
        )
        suggestions: list[Suggestion] = []
        opcodes: list[tuple[str, int, int, int, int]] = []
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "replace" and i2 - i1 == j2 - j1 and i2 - i1 > 1:
                opcodes.extend(
                    ("replace", source_index, source_index + 1, target_index, target_index + 1)
                    for source_index, target_index in zip(
                        range(i1, i2), range(j1, j2), strict=True
                    )
                )
            else:
                opcodes.append((opcode, i1, i2, j1, j2))

        for opcode, i1, i2, j1, j2 in opcodes:
            if opcode == "equal":
                continue
            start, end = _source_offsets(original, source, i1, i2)
            before = _slice_for_tokens(original, source, i1, i2)
            after = _slice_for_tokens(corrected, target, j1, j2)
            kind = {
                "replace": EditKind.replacement,
                "insert": EditKind.insertion,
                "delete": EditKind.deletion,
            }[opcode]
            digest = hashlib.sha1(
                f"{start}:{end}:{before}:{after}".encode(), usedforsecurity=False
            ).hexdigest()[:12]
            suggestions.append(
                Suggestion(
                    id=digest,
                    start=start,
                    end=end,
                    original=before,
                    replacement=after,
                    kind=kind,
                    message=self._message(kind, before, after),
                )
            )
            if len(suggestions) >= limit:
                break
        return suggestions

    @staticmethod
    def _message(kind: EditKind, before: str, after: str) -> str:
        if kind is EditKind.insertion:
            return f'Insert "{after}"'
        if kind is EditKind.deletion:
            return f'Remove "{before}"'
        return f'Change "{before}" to "{after}"'
