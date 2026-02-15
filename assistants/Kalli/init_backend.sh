#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KEYS_FILE="../../shared/.keys"
if [ -f "$KEYS_FILE" ]; then set -a; source "$KEYS_FILE"; set +a; fi
if [ -f .env ]; then set -a; source .env; set +a; fi

uvicorn backend.webserver:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
