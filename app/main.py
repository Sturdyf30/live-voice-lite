from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import get_settings
from .conversation import ConversationStore
from .llm import LanguageModel
from .stt import SpeechToText
from .tts import TextToSpeech

settings = get_settings()
store = ConversationStore(settings.history_turns)
stt = SpeechToText(settings)
llm = LanguageModel(settings)
tts = TextToSpeech(settings)


class TextTurn(BaseModel):
    session_id: str
    text: str
    voice: str | None = None
    speed: float | None = None


async def cleanup_audio_loop() -> None:
    while True:
        cutoff = time.time() - (settings.audio_ttl_minutes * 60)
        for path in settings.audio_dir.glob("*.mp3"):
            with suppress(OSError):
                if path.stat().st_mtime < cutoff:
                    path.unlink()
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cleanup_task = asyncio.create_task(cleanup_audio_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(title=settings.app_name, lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "name": settings.app_name,
        "llm": {
            "backend": settings.llm_backend,
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
        },
        "stt": {"backend": settings.stt_backend, "model": settings.stt_model},
        "tts": {
            "backend": settings.tts_backend,
            "base_url": settings.tts_base_url,
            "model": settings.tts_model,
            "voice": settings.tts_voice,
            "speed": settings.tts_speed,
        },
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "max_audio_seconds": settings.max_audio_seconds,
        },
    }


def validate_session_id(session_id: str) -> str:
    session_id = session_id.strip()
    if not session_id or len(session_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid session id.")
    return session_id


async def probe_audio_duration(audio_path: Path) -> float | None:
    """Return media duration using ffprobe, or None when ffprobe is unavailable."""

    try:
        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return None

    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=10)
    except TimeoutError:
        process.kill()
        await process.wait()
        return None

    if process.returncode != 0:
        return None
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return None


async def run_turn(
    *,
    session_id: str,
    user_text: str,
    voice: str | None,
    speed: float | None,
    timing: dict[str, float],
) -> dict:
    session_id = validate_session_id(session_id)
    user_text = user_text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="No speech or text was detected.")

    async with store.lock(session_id):
        llm_started = time.perf_counter()
        assistant_text = await llm.respond(store.messages(session_id), user_text)
        timing["llm_ms"] = round((time.perf_counter() - llm_started) * 1000)
        store.append_turn(session_id, user_text, assistant_text)

        audio_id: str | None = None
        if settings.tts_backend != "disabled":
            audio_id = f"{uuid.uuid4().hex}.mp3"
            audio_path = settings.audio_dir / audio_id
            tts_started = time.perf_counter()
            try:
                await tts.synthesize(
                    assistant_text,
                    audio_path,
                    voice=voice,
                    speed=speed,
                )
                timing["tts_ms"] = round((time.perf_counter() - tts_started) * 1000)
            except Exception:
                # A dead TTS service should not destroy a useful model response.
                audio_id = None
                timing["tts_ms"] = -1

    timing["total_ms"] = round(sum(value for value in timing.values() if value > 0))
    return {
        "user_text": user_text,
        "assistant_text": assistant_text,
        "audio_url": f"/audio/{audio_id}" if audio_id else None,
        "timing": timing,
    }


@app.post("/api/turn/audio")
async def audio_turn(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    voice: str | None = Form(None),
    speed: float | None = Form(None),
) -> dict:
    session_id = validate_session_id(session_id)
    suffix = Path(audio.filename or "turn.webm").suffix[:10] or ".webm"
    upload_path = settings.data_dir / f"upload-{uuid.uuid4().hex}{suffix}"
    size = 0

    try:
        with upload_path.open("wb") as handle:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Audio exceeds {settings.max_upload_mb} MB.",
                    )
                handle.write(chunk)

        duration = await probe_audio_duration(upload_path)
        if duration is not None and duration > settings.max_audio_seconds:
            raise HTTPException(
                status_code=413,
                detail=f"Audio exceeds {settings.max_audio_seconds} seconds.",
            )

        timing: dict[str, float] = {}
        stt_started = time.perf_counter()
        user_text = await stt.transcribe(upload_path)
        timing["stt_ms"] = round((time.perf_counter() - stt_started) * 1000)
        return await run_turn(
            session_id=session_id,
            user_text=user_text,
            voice=voice,
            speed=speed,
            timing=timing,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        with suppress(OSError):
            upload_path.unlink()


@app.post("/api/turn/text")
async def text_turn(turn: TextTurn) -> dict:
    try:
        return await run_turn(
            session_id=turn.session_id,
            user_text=turn.text,
            voice=turn.voice,
            speed=turn.speed,
            timing={},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/reset/{session_id}")
async def reset(session_id: str) -> dict:
    store.reset(validate_session_id(session_id))
    return {"ok": True}


@app.get("/audio/{audio_id}")
async def audio_file(audio_id: str) -> FileResponse:
    if not audio_id.endswith(".mp3") or any(char not in "0123456789abcdef.mp3" for char in audio_id):
        raise HTTPException(status_code=404, detail="Audio not found.")
    path = settings.audio_dir / audio_id
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found.")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
