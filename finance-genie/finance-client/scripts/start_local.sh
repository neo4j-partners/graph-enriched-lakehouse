#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${APP_DIR}/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${APP_DIR}/.env.local"
  set +a
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8501}"

cd "${APP_DIR}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/finance-genie-client-uv-cache}"

echo "Starting Finance Genie Client"
echo "App:  ${APP_DIR}"
echo "URL:  http://${HOST}:${PORT}"
echo

exec uv run \
  --with-requirements requirements.txt \
  streamlit run app.py \
  --server.address "${HOST}" \
  --server.port "${PORT}" \
  --server.headless true
