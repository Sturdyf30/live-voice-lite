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

The default audio path is local, so your recurring cost is only whatever model/provider Hermes already uses. You can also point the brain at Ollama, llama.cpp, vLLM, an OpenAI-compatible provider, or the OpenAI Responses API.

## What it includes

- Hold-to-talk with mouse, touch, or Space.
- Optional hands-free endpointing after roughly 900 ms of silence.
- Barge-in: beginning another recording stops current playback.
- Local `faster-whisper` STT using CPU INT8.
- Local Kokoro TTS through an OpenAI-compatible endpoint.
- Hermes Agent as the default backend.
- Typed-message fallback.
- In-memory conversation history with a reset button.
- STT, Hermes, and TTS latency shown after each turn.
- API keys stay server-side; the browser never receives them.

## Fedora setup

### 1. Extract and install

```bash
cd live-voice-lite
./setup-fedora.sh
```

The first local Whisper turn downloads the configured model. The default `base.en` model is chosen for lower CPU latency. Change `STT_MODEL=small.en` in `.env` for better recognition at the cost of additional latency and memory.

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

With Docker Compose, this is equivalent:

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

This is API-billed and is unrelated to a ChatGPT subscription.

### Local transcription

```dotenv
STT_BACKEND=local
STT_MODEL=base.en
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
```

For an API transcription server, switch `STT_BACKEND=openai_compatible` and configure its URL, key, and model.

### Kokoro voices

The default is:

```dotenv
TTS_VOICE=af_heart
TTS_SPEED=1.05
```

Other common Kokoro voices include `af_bella`, `af_sky`, `am_adam`, and weighted mixes such as `af_bella(2)+af_sky(1)`. The UI voice box overrides the environment default per turn.

### Disable TTS

```dotenv
TTS_BACKEND=disabled
```

## Smoke tests

```bash
source .venv/bin/activate
python -m pytest -q
curl http://127.0.0.1:8766/api/health
```

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

## Security boundaries

- The web server binds to `127.0.0.1` by default. Do not expose it publicly without authentication and HTTPS.
- The Hermes and Kokoro ports in the included examples also bind only to localhost.
- Audio uploads are deleted after transcription. Generated replies are deleted after the configured TTL.
- Conversation history is held in RAM and disappears when the app stops.
- Hermes tools execute on the machine where `hermes gateway` runs. Keep Hermes command-approval and sandbox settings appropriate for voice input.

## Why this is “Lite”

A true full-duplex speech-to-speech system streams microphone audio, model tokens, and synthesized audio simultaneously. This version deliberately avoids that complexity and expense. It records one utterance, processes it, and returns one spoken answer, while still supporting interruption and automatic endpointing.
