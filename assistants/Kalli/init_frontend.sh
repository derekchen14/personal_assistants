#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/frontend"

npm run dev -- --port "${FRONTEND_PORT:-5173}"
