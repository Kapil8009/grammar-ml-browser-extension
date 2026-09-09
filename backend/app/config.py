from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    model_name: str = "jbochi/coedit-small"
    model_prefix: str = "Fix the grammar: "
    model_revision: str = "main"
    use_safetensors: bool = True
    device: str = "auto"
    max_input_tokens: int = 384
    max_new_tokens: int = 256
    num_beams: int = 4
    allowed_origins: tuple[str, ...] = ("*",)
    api_key: str | None = None
    max_text_chars: int = 12_000
    preload_model: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        defaults = cls()
        origins = tuple(
            item.strip()
            for item in os.getenv("GEC_ALLOWED_ORIGINS", "*").split(",")
            if item.strip()
        )
        return cls(
            model_name=os.getenv("GEC_MODEL_NAME", defaults.model_name),
            model_prefix=os.getenv("GEC_MODEL_PREFIX", defaults.model_prefix),
            model_revision=os.getenv("GEC_MODEL_REVISION", defaults.model_revision),
            use_safetensors=_as_bool(
                os.getenv("GEC_USE_SAFETENSORS"), defaults.use_safetensors
            ),
            device=os.getenv("GEC_DEVICE", defaults.device),
            max_input_tokens=int(os.getenv("GEC_MAX_INPUT_TOKENS", defaults.max_input_tokens)),
            max_new_tokens=int(os.getenv("GEC_MAX_NEW_TOKENS", defaults.max_new_tokens)),
            num_beams=int(os.getenv("GEC_NUM_BEAMS", defaults.num_beams)),
            allowed_origins=origins or ("*",),
            api_key=os.getenv("GEC_API_KEY") or None,
            max_text_chars=int(os.getenv("GEC_MAX_TEXT_CHARS", defaults.max_text_chars)),
            preload_model=_as_bool(os.getenv("GEC_PRELOAD_MODEL")),
            log_level=os.getenv("GEC_LOG_LEVEL", defaults.log_level),
        )
