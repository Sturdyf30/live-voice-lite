from __future__ import annotations

from pathlib import Path

import httpx

from .config import Settings
from .text_utils import text_for_speech


class TextToSpeech:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice: str | None = None,
        speed: float | None = None,
    ) -> bool:
        if self.settings.tts_backend == "disabled":
            return False

        spoken_text = text_for_speech(text, self.settings.tts_max_chars)
        selected_voice = (voice or self.settings.tts_voice).strip()
        selected_speed = min(2.0, max(0.5, speed or self.settings.tts_speed))

        headers = {"Content-Type": "application/json"}
        if self.settings.tts_api_key:
            headers["Authorization"] = f"Bearer {self.settings.tts_api_key}"

        payload = {
            "model": self.settings.tts_model,
            "voice": selected_voice,
            "input": spoken_text,
            "response_format": "mp3",
            "speed": selected_speed,
        }
        async with httpx.AsyncClient(timeout=self.settings.tts_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.tts_base_url}/audio/speech",
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            detail = response.text[:1000]
            raise RuntimeError(f"TTS returned HTTP {response.status_code}: {detail}")
        if not response.content:
            raise RuntimeError("TTS returned an empty audio file.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
