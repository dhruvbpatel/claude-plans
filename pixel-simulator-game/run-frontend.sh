#!/usr/bin/env bash
# Install npm deps if needed and start the Vite dev server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$ROOT/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required. Install Node.js from https://nodejs.org/ then re-run." >&2
  exit 1
fi

echo "Installing frontend dependencies ..."
cd "$FRONTEND"
npm install

echo "Starting frontend on http://localhost:5173 ..."
exec npm run dev
