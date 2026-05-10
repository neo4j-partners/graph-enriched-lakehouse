#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${APP_DIR}/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
elif [[ -f "${APP_DIR}/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${APP_DIR}/.env.local"
  set +a
fi

PORT="${PORT:-8501}"

PIDS="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"

if [[ -z "${PIDS}" ]]; then
  echo "No Finance Genie Client server found on port ${PORT}."
  exit 0
fi

echo "Stopping local server on port ${PORT}: ${PIDS}"
kill ${PIDS}

for _ in $(seq 1 10); do
  if ! lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Stopped."
    exit 0
  fi
  sleep 1
done

echo "Server did not stop after 10 seconds; sending SIGKILL."
kill -9 ${PIDS} 2>/dev/null || true
echo "Stopped."
