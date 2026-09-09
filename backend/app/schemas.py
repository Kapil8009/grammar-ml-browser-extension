from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class EditKind(str, Enum):
    replacement = "replacement"
    insertion = "insertion"
    deletion = "deletion"


class CorrectionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    max_suggestions: int = Field(default=50, ge=1, le=200)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain a non-whitespace character")
        return value


class BatchCorrectionRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)
    max_suggestions: int = Field(default=50, ge=1, le=200)

    @field_validator("texts")
    @classmethod
    def reject_blank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("texts cannot contain blank items")
        return value


class Suggestion(BaseModel):
    id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    original: str
    replacement: str
    kind: EditKind
    message: str


class CorrectionResponse(BaseModel):
    original: str
    corrected: str
    changed: bool
    suggestions: list[Suggestion]
    model: str
    latency_ms: float = Field(ge=0)


class BatchCorrectionResponse(BaseModel):
    results: list[CorrectionResponse]


class ModelInfo(BaseModel):
    name: str
    backend: str
    loaded: bool
