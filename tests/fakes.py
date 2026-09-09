from __future__ import annotations


class FakeCorrectionModel:
    def __init__(self, corrections: dict[str, str] | None = None) -> None:
        self.corrections = corrections or {}
        self._loaded = False

    @property
    def name(self) -> str:
        return "test/fake-gec"

    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def correct_batch(self, texts: list[str]) -> list[str]:
        self.load()
        return [self.corrections.get(text, text) for text in texts]
