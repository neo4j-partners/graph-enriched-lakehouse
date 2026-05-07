#!/usr/bin/env bash
# Start the local graph-specialist HTTP server.
#
# Usage:
#   ./scripts/start_local.sh [--host 127.0.0.1] [--port 8787]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"
HOST="127.0.0.1"
PORT="8787"
STATE_DIR="${DEMO_DIR}/.local"
PID_FILE="${STATE_DIR}/agent-server.pid"
LOG_FILE="${STATE_DIR}/agent-server.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || { echo "Error: --host requires a value" >&2; exit 1; }
      HOST="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || { echo "Error: --port requires a value" >&2; exit 1; }
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Local server already running with PID $(cat "$PID_FILE")."
  exit 0
fi

mkdir -p "$STATE_DIR"
cd "$DEMO_DIR"

nohup /usr/bin/env PYTHONUNBUFFERED=1 uv run python scripts/local_agent_server.py --host "$HOST" --port "$PORT" \
  >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

sleep 2
if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Local server failed to start. Log follows:" >&2
  sed -n '1,160p' "$LOG_FILE" >&2
  rm -f "$PID_FILE"
  exit 1
fi

echo "Started local graph specialist server:"
echo "  URL: http://${HOST}:${PORT}"
echo "  PID: $(cat "$PID_FILE")"
echo "  Log: $LOG_FILE"
