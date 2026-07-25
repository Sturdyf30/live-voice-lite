#!/usr/bin/env bash
set -euo pipefail
IMAGE="ghcr.io/remsky/kokoro-fastapi-cpu:latest"

if command -v docker >/dev/null 2>&1; then
  exec docker run --rm --name live-voice-lite-kokoro -p 127.0.0.1:8880:8880 "$IMAGE"
elif command -v podman >/dev/null 2>&1; then
  exec podman run --rm --name live-voice-lite-kokoro -p 127.0.0.1:8880:8880 "$IMAGE"
else
  echo "Install Docker or Podman, then rerun this script." >&2
  exit 1
fi
