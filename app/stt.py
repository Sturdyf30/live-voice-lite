from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from .config import Settings


class SpeechToText:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Any | None = None
        self._model_lock = asyncio.Lock()

    async def transcribe(self, audio_path: Path) -> str:
        if self.settings.stt_backend == "local":
            return await self._transcribe_local(audio_path)
        return await self._transcribe_http(audio_path)

    async def _load_local_model(self) -> Any:
        if self._model is not None:
            return self._model
        async with self._model_lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise RuntimeError(
                        "Local STT requires faster-whisper. Run: pip install -r requirements.txt"
                    ) from exc
                self._model = await asyncio.to_thread(
                    WhisperModel,
                    self.settings.stt_model,
                    device=self.settings.stt_device,
                    compute_type=self.settings.stt_compute_type,
                    cpu_threads=self.settings.stt_cpu_threads,
                    num_workers=1,
                )
        return self._model

    async def _transcribe_local(self, audio_path: Path) -> str:
        model = await self._load_local_model()

        def run() -> str:
            segments, _info = model.transcribe(
                str(audio_path),
                language=self.settings.stt_language,
                beam_size=1,
                best_of=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()

        text = await asyncio.to_thread(run)
        if not text:
            raise RuntimeError("No speech was detected.")
        return text

    async def _transcribe_http(self, audio_path: Path) -> str:
        headers = {}
        if self.settings.stt_api_key:
            headers["Authorization"] = f"Bearer {self.settings.stt_api_key}"

        data = {"model": self.settings.stt_model}
        if self.settings.stt_language:
            data["language"] = self.settings.stt_language

        async with httpx.AsyncClient(timeout=self.settings.stt_timeout_seconds) as client:
            with audio_path.open("rb") as handle:
                response = await client.post(
                    f"{self.settings.stt_base_url}/audio/transcriptions",
                    headers=headers,
                    data=data,
                    files={"file": (audio_path.name, handle, "application/octet-stream")},
                )
        response.raise_for_status()
        text = str(response.json().get("text", "")).strip()
        if not text:
            raise RuntimeError("The transcription service returned no text.")
        return text
