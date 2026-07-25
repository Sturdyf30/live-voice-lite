#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Check the Hermes API key before continuing."
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Virtual environment is missing. Run ./setup-fedora.sh first." >&2
  exit 1
fi

source .venv/bin/activate

if ! python -c 'import fastapi, uvicorn, httpx, faster_whisper' >/dev/null 2>&1; then
  echo "Python dependencies are missing. Run ./setup-fedora.sh first." >&2
  exit 1
fi

set -a
source .env
set +a

case "${HOST:-127.0.0.1}" in
  127.0.0.1|localhost|::1) ;;
  *)
    if [[ "${LLM_API_KEY:-change-me-local-dev}" == "change-me-local-dev" ]]; then
      echo "Refusing non-localhost binding while LLM_API_KEY uses the example value." >&2
      echo "Set a real key or bind HOST to 127.0.0.1." >&2
      exit 1
    fi
    ;;
esac

exec uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8766}"
