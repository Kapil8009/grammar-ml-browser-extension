from __future__ import annotations

import logging
import threading
from typing import Any

from backend.app.config import Settings


logger = logging.getLogger(__name__)


class HuggingFaceSeq2SeqModel:
    """Lazy-loaded Transformers model implementing the CorrectionModel protocol."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._device = "cpu"
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self.settings.model_name

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self.loaded:
            return
        with self._lock:
            if self.loaded:
                return
            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "ML dependencies are missing. Install with: pip install -e '.[ml]'"
                ) from exc

            device = self.settings.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading %s on %s", self.name, device)
            tokenizer = AutoTokenizer.from_pretrained(
                self.name,
                revision=self.settings.model_revision,
                trust_remote_code=False,
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                self.name,
                revision=self.settings.model_revision,
                trust_remote_code=False,
                use_safetensors=True,
            )
            model.to(device)
            model.eval()
            self._torch = torch
            self._tokenizer = tokenizer
            self._model = model
            self._device = device
            logger.info("Model loaded")

    def correct_batch(self, texts: list[str]) -> list[str]:
        self.load()
        prompts = [f"{self.settings.model_prefix}{text}" for text in texts]
        encoded = self._tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.settings.max_input_tokens,
        ).to(self._device)
        with self._torch.inference_mode():
            generated = self._model.generate(
                **encoded,
                max_new_tokens=self.settings.max_new_tokens,
                num_beams=self.settings.num_beams,
                early_stopping=True,
                no_repeat_ngram_size=3,
            )
        outputs = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [output.strip() for output in outputs]
