# Live Voice Lite

A cheap, self-hosted, browser-based voice interface for Hermes Agent.

It is intentionally **not** a full speech-to-speech Realtime clone. It is a fast turn-based loop with push-to-talk, optional silence detection, playback interruption, a transcript, and timing diagnostics:

```text
browser microphone
  → local faster-whisper transcription
  → Hermes Agent API with its tools/memory
  → local Kokoro speech
  → browser audio playback
```

The default audio path is local, so your recurring cost is only whatever model/provider Hermes already uses. You can also point the brain at Ollama, llama.cpp, vLLM, another OpenAI-compatible provider, or the OpenAI Responses API.

## What it includes

- Hold-to-talk with mouse, touch, or Space.
- Optional hands-free endpointing after roughly 500 ms of silence.
- Barge-in: beginning another recording stops current playback.
- Local `faster-whisper` STT using CPU INT8.
- Local Kokoro TTS through an OpenAI-compatible endpoint.
- Hermes Agent as the default backend.
- Typed-message fallback.
- In-memory conversation history with a reset button.
- STT, Hermes, and TTS latency shown after each turn.
- Readiness checks for the configured Hermes and Kokoro endpoints.
- API keys stay server-side; the browser never receives them.

## Fedora setup

### 1. Install

```bash
cd live-voice-lite
./setup-fedora.sh
```

The first local Whisper turn downloads the configured model. The default is `base.en`, which is a practical CPU balance between latency and recognition quality. Use `tiny.en` for lower latency or `small.en` for better recognition.

### 2. Enable Hermes Agent's API server

```bash
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY change-me-local-dev
hermes gateway stop
hermes gateway
```

Hermes should report that its API server is listening at `http://127.0.0.1:8642`. Keep the key in `.env` synchronized with `API_SERVER_KEY`.

### 3. Start local Kokoro TTS

In a second terminal:

```bash
cd live-voice-lite
./start-kokoro.sh
```

The first container pull is large because it contains the runtime and model. After it starts, Kokoro listens only on localhost at port `8880`.

With Docker Compose:

```bash
docker compose up -d kokoro
```

### 4. Start Live Voice Lite

In a third terminal:

```bash
cd live-voice-lite
./run.sh
```

Open:

```text
http://127.0.0.1:8766
```

Allow microphone access. Hold the microphone button or Space, speak, and release.

`run.sh` does not reinstall packages on every launch. If the virtual environment or dependencies are missing, rerun `./setup-fedora.sh`.

## Configuration

Copy `.env.example` to `.env`; `run.sh` does this automatically when needed.

### Hermes backend

```dotenv
LLM_BACKEND=chat_completions
LLM_BASE_URL=http://127.0.0.1:8642/v1
LLM_API_KEY=change-me-local-dev
LLM_MODEL=hermes-agent
```

Because the full conversation is submitted to Hermes each turn, the app keeps only the most recent `HISTORY_TURNS`. Hermes still runs its normal agent toolset on the machine hosting the gateway.

### Fully local LLM instead of Hermes

Any OpenAI-compatible `/v1/chat/completions` endpoint works. Example for Ollama:

```dotenv
LLM_BACKEND=chat_completions
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=local
LLM_MODEL=qwen3:8b
```

### OpenAI Responses API

```dotenv
LLM_BACKEND=openai_responses
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=YOUR_OPENAI_MODEL
```

This is API-billed and unrelated to a ChatGPT subscription.

### Local transcription

```dotenv
STT_BACKEND=local
STT_MODEL=base.en
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_CPU_THREADS=8
```

For an API transcription server, switch `STT_BACKEND=openai_compatible` and configure its URL, key, and model.

### Kokoro voices

```dotenv
TTS_VOICE=af_heart
TTS_SPEED=1.05
```

Other common Kokoro voices include `af_bella`, `af_sky`, and `am_adam`. Weighted mixes such as `af_bella(2)+af_sky(1)` may also work depending on the Kokoro server version. The UI voice box overrides the environment default per turn.

### Disable TTS

```dotenv
TTS_BACKEND=disabled
```

## Health and smoke tests

```bash
source .venv/bin/activate
python -m pytest -q
curl http://127.0.0.1:8766/api/health
```

The health response includes both configuration and live reachability information for Hermes and Kokoro. A service returning a normal 4xx response still counts as reachable; connection failures and 5xx responses do not.

Test Hermes directly:

```bash
curl http://127.0.0.1:8642/v1/chat/completions \
  -H 'Authorization: Bearer change-me-local-dev' \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"Reply with READY."}]}'
```

Test Kokoro directly:

```bash
curl http://127.0.0.1:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","voice":"af_heart","input":"Voice is working.","response_format":"mp3"}' \
  --output test.mp3
```

## Troubleshooting

**The page loads but Hermes does not answer:** Confirm `hermes gateway` is running, the API server is enabled, and `LLM_API_KEY` matches Hermes's `API_SERVER_KEY`.

**The text response appears but no voice plays:** Check that Kokoro is reachable at `http://127.0.0.1:8880`. TTS failures no longer discard the Hermes response; the server logs the failure and returns a warning with the turn.

**The first transcription is slow:** The Whisper model is loaded lazily on the first turn. Later turns reuse it.

**Hands-free mode cuts off pauses:** Increase the 500 ms threshold in `app/static/app.js`, or use push-to-talk.

## Security boundaries

- The web server binds to `127.0.0.1` by default. Do not expose it publicly without authentication and HTTPS.
- `run.sh` refuses a non-localhost bind while the example API key is still configured.
- Hermes and Kokoro also bind only to localhost in the included examples.
- Audio uploads are deleted after transcription. Generated replies are deleted after the configured TTL.
- Conversation history is held in RAM and disappears when the app stops.
- Hermes tools execute on the machine where `hermes gateway` runs. Keep Hermes command-approval and sandbox settings appropriate for voice input.

## Development

```bash
source .venv/bin/activate
python -m compileall -q app tests
python -m pytest -q
```

GitHub Actions runs the same checks on Python 3.11 and 3.12.

## Why this is “Lite”

A true full-duplex speech-to-speech system streams microphone audio, model tokens, and synthesized audio simultaneously. This version deliberately avoids that complexity and expense. It records one utterance, processes it, and returns one spoken answer, while still supporting interruption and automatic endpointing.

## License

MIT. See [LICENSE](LICENSE).
