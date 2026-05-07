#!/usr/bin/env bash
# Stop the local graph-specialist HTTP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${DEMO_DIR}/.local/agent-server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No local server PID file found."
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped local server PID $PID."
else
  echo "Local server PID $PID was not running."
fi

rm -f "$PID_FILE"
