from __future__ import annotations

from time import perf_counter

from backend.app.core.interfaces import CorrectionModel
from backend.app.core.postprocessing import DiffPostprocessor
from backend.app.core.preprocessing import TextPreprocessor
from backend.app.schemas import CorrectionResponse


class CorrectionService:
    def __init__(
        self,
        model: CorrectionModel,
        preprocessor: TextPreprocessor | None = None,
        postprocessor: DiffPostprocessor | None = None,
    ) -> None:
        self.model = model
        self.preprocessor = preprocessor or TextPreprocessor()
        self.postprocessor = postprocessor or DiffPostprocessor()

    def correct(self, text: str, max_suggestions: int = 50) -> CorrectionResponse:
        started = perf_counter()
        prepared = self.preprocessor.prepare(text)
        corrected_segments = self.model.correct_batch(list(prepared.segments))
        corrected = prepared.rebuild(corrected_segments)
        suggestions = self.postprocessor.suggestions(text, corrected, max_suggestions)
        return CorrectionResponse(
            original=text,
            corrected=corrected,
            changed=text != corrected,
            suggestions=suggestions,
            model=self.model.name,
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )
