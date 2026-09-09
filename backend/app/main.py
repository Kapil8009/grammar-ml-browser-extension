from __future__ import annotations

import asyncio
import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import Settings
from backend.app.core.interfaces import CorrectionModel
from backend.app.models.huggingface_seq2seq import HuggingFaceSeq2SeqModel
from backend.app.schemas import (
    BatchCorrectionRequest,
    BatchCorrectionResponse,
    CorrectionRequest,
    CorrectionResponse,
    ModelInfo,
)
from backend.app.services.correction import CorrectionService


def create_app(
    settings: Settings | None = None,
    model: CorrectionModel | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    correction_model = model or HuggingFaceSeq2SeqModel(config)
    service = CorrectionService(correction_model)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if config.preload_model:
            await asyncio.to_thread(correction_model.load)
        yield

    application = FastAPI(
        title="Grammar ML API",
        description="Transformer-based grammatical error correction",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = config
    application.state.model = correction_model
    application.state.service = service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    async def authorize(x_api_key: str | None = Header(default=None)) -> None:
        if config.api_key and not (
            x_api_key and hmac.compare_digest(x_api_key, config.api_key)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    def validate_size(texts: list[str]) -> None:
        if any(len(text) > config.max_text_chars for text in texts):
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Each text is limited to {config.max_text_chars} characters",
            )

    @application.exception_handler(RuntimeError)
    async def runtime_error_handler(_: Request, exc: RuntimeError) -> JSONResponse:
        logging.getLogger(__name__).exception("Correction backend failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", tags=["system"])
    async def ready() -> dict[str, str | bool]:
        return {"status": "ready", "model_loaded": correction_model.loaded}

    @application.get("/v1/models/current", response_model=ModelInfo, tags=["models"])
    async def current_model(_: None = Depends(authorize)) -> ModelInfo:
        return ModelInfo(
            name=correction_model.name,
            backend=type(correction_model).__name__,
            loaded=correction_model.loaded,
        )

    @application.post("/v1/correct", response_model=CorrectionResponse, tags=["correction"])
    async def correct(
        payload: CorrectionRequest,
        _: None = Depends(authorize),
    ) -> CorrectionResponse:
        validate_size([payload.text])
        return service.correct(payload.text, payload.max_suggestions)

    @application.post(
        "/v1/correct/batch", response_model=BatchCorrectionResponse, tags=["correction"]
    )
    async def correct_batch(
        payload: BatchCorrectionRequest,
        _: None = Depends(authorize),
    ) -> BatchCorrectionResponse:
        validate_size(payload.texts)
        results = [service.correct(text, payload.max_suggestions) for text in payload.texts]
        return BatchCorrectionResponse(results=results)

    return application


app = create_app()
