#!/usr/bin/env bash
# Create/reuse a Python venv, install deps, and start the FastAPI server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3 is required. Install it from https://www.python.org/downloads/ then re-run." >&2
  exit 1
fi

if [[ -x "$BACKEND/.venv/bin/python" ]]; then
  VENV="$BACKEND/.venv"
elif [[ -x "$BACKEND/venv/bin/python" ]]; then
  VENV="$BACKEND/venv"
else
  echo "Creating virtualenv at backend/.venv ..."
  "$PYTHON" -m venv "$BACKEND/.venv"
  VENV="$BACKEND/.venv"
fi

echo "Installing backend dependencies ..."
"$VENV/bin/python" -m pip install -q -r "$BACKEND/requirements.txt"

if [[ ! -f "$ROOT/.env" && -f "$ROOT/.env.example" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Copied .env.example to .env"
fi

echo "Starting API on http://127.0.0.1:8000 ..."
cd "$BACKEND"
exec "$VENV/bin/python" -m uvicorn app.main:app --reload --port 8000
