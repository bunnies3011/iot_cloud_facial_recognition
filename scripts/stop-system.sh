#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.webapp.pid"

PI_HOST="${PI_HOST:-}"
PI_SERVICE="${PI_SERVICE:-iot-face-client.service}"

if [[ -n "$PI_HOST" ]]; then
  ssh "$PI_HOST" "sudo systemctl stop $PI_SERVICE"
fi

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
  fi
  rm -f "$PID_FILE"
fi

echo "System stopped"
