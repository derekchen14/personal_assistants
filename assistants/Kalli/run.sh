#!/usr/bin/env bash
# Start Kalli backend + frontend.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment (shared keys first, then local .env overrides)
KEYS_FILE="$SCRIPT_DIR/../../shared/.keys"
if [ -f "$KEYS_FILE" ]; then
    set -a; source "$KEYS_FILE"; set +a
fi
if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

cleanup() {
    echo "Shutting down..."
    kill 0 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "Starting Kalli backend on port $PORT..."
uvicorn backend.webserver:app --host 0.0.0.0 --port "$PORT" --reload &

echo "Starting Kalli frontend on port $FRONTEND_PORT..."
cd frontend && npm run dev -- --port "$FRONTEND_PORT" &

wait
