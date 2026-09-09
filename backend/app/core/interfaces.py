from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CorrectionModel(Protocol):
    """The replaceable boundary between the API and an inference backend."""

    @property
    def name(self) -> str: ...

    @property
    def loaded(self) -> bool: ...

    def load(self) -> None: ...

    def correct_batch(self, texts: list[str]) -> list[str]: ...
