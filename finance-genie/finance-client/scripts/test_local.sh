#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${APP_DIR}/.." && pwd)"

LOG_FILE="$(mktemp -t finance-genie-client.XXXXXX.log)"

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

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18501}"
URL="http://${HOST}:${PORT}"

cleanup() {
  if [[ -n "${APP_PID:-}" ]] && kill -0 "${APP_PID}" >/dev/null 2>&1; then
    kill "${APP_PID}" >/dev/null 2>&1 || true
    wait "${APP_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${LOG_FILE}"
}
trap cleanup EXIT

cd "${APP_DIR}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/finance-genie-client-uv-cache}"

echo "Compiling app modules"
python -m py_compile \
  app.py \
  backend.py \
  pages/1_GDS_Enhanced_Graph_Schema.py \
  pages/2_Executive_Comparison.py \
  pages/3_Question_Surface.py \
  pages/4_Business_Value.py \
  pages/5_Data_Lineage.py \
  pages/6_MCP_Full_Schema.py

echo "Starting smoke-test server on ${URL}"
uv run \
  --with-requirements requirements.txt \
  streamlit run app.py \
  --server.address "${HOST}" \
  --server.port "${PORT}" \
  --server.headless true \
  >"${LOG_FILE}" 2>&1 &
APP_PID="$!"

for _ in $(seq 1 30); do
  if curl -fsS "${URL}" >/dev/null 2>&1; then
    echo "Local smoke test passed: ${URL}"
    exit 0
  fi

  if ! kill -0 "${APP_PID}" >/dev/null 2>&1; then
    echo "Streamlit exited before becoming ready"
    cat "${LOG_FILE}"
    exit 1
  fi

  sleep 1
done

echo "Timed out waiting for ${URL}"
cat "${LOG_FILE}"
exit 1
