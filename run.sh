#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Check the Hermes API key before continuing."
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

set -a
source .env
set +a
exec uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8766}"
