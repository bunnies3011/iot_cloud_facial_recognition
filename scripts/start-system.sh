#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEBAPP_DIR="$ROOT_DIR/webapp"
PID_FILE="$ROOT_DIR/.webapp.pid"

PI_HOST="${PI_HOST:-}"
PI_SERVICE="${PI_SERVICE:-iot-face-client.service}"

if [[ -n "$PI_HOST" ]]; then
  ssh "$PI_HOST" "sudo systemctl start $PI_SERVICE && systemctl --no-pager --full status $PI_SERVICE"
fi

cd "$WEBAPP_DIR"
if [[ ! -d node_modules ]]; then
  npm install
fi

if [[ ! -f .next/BUILD_ID ]]; then
  npm run build
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Web dashboard already running on PID $(cat "$PID_FILE")"
else
  nohup npm run dev > "$ROOT_DIR/webapp.log" 2>&1 &
  echo "$!" > "$PID_FILE"
fi

echo "Dashboard: http://localhost:3000"
