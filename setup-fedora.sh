#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

sudo dnf install -y python3 python3-pip ffmpeg espeak-ng
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
[[ -f .env ]] || cp .env.example .env

echo
echo "Installed Live Voice Lite. Next:"
echo "  1. Enable the Hermes API server as described in README.md."
echo "  2. Start Kokoro: ./start-kokoro.sh"
echo "  3. Start the app: ./run.sh"
