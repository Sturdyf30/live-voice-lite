from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Live Voice Lite"
    host: str = "127.0.0.1"
    port: int = 8766
    data_dir: Path = Path("data")
    max_upload_mb: int = 12
    max_audio_seconds: int = 45
    audio_ttl_minutes: int = 60

    # Hermes is the default. Any OpenAI-compatible /v1/chat/completions server works.
    llm_backend: Literal["chat_completions", "openai_responses"] = "chat_completions"
    llm_base_url: str = "http://127.0.0.1:8642/v1"
    llm_api_key: str = "change-me-local-dev"
    llm_model: str = "hermes-agent"
    llm_timeout_seconds: float = 180.0
    llm_max_output_tokens: int = 700
    history_turns: int = 12
    system_prompt: str = (
        "You are speaking aloud in a low-latency voice conversation. "
        "Answer naturally and directly. Keep ordinary replies under about 120 words unless "
        "the user asks for detail. Avoid markdown tables. Read code only when specifically requested."
    )

    # Local faster-whisper is free and is the default.
    stt_backend: Literal["local", "openai_compatible"] = "local"
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_cpu_threads: int = 8
    stt_language: str | None = "en"
    stt_base_url: str = "https://api.openai.com/v1"
    stt_api_key: str = ""
    stt_timeout_seconds: float = 90.0

    # Kokoro-FastAPI is OpenAI-compatible and runs locally at port 8880.
    tts_backend: Literal["openai_compatible", "disabled"] = "openai_compatible"
    tts_base_url: str = "http://127.0.0.1:8880/v1"
    tts_api_key: str = "not-needed"
    tts_model: str = "kokoro"
    tts_voice: str = "af_heart"
    tts_speed: float = 1.05
    tts_timeout_seconds: float = 120.0
    tts_max_chars: int = 1800

    @field_validator("llm_base_url", "stt_base_url", "tts_base_url")
    @classmethod
    def trim_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("tts_speed")
    @classmethod
    def validate_speed(cls, value: float) -> float:
        return min(2.0, max(0.5, value))

    @field_validator("history_turns")
    @classmethod
    def validate_history(cls, value: int) -> int:
        return min(50, max(1, value))

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    return settings
