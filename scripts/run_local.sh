#!/usr/bin/env bash
# Quickstart: sets up and runs the backend in MOCK_MODE with zero external dependencies.
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -r requirements.txt

export MOCK_MODE=true
echo "Starting Knowledge Intelligence Platform (MOCK_MODE=true) on http://localhost:8000"
echo "Open frontend/index.html in a browser, or use http://localhost:8000/docs for the API console."
uvicorn app.main:app --reload --port 8000
