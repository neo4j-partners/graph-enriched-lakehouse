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

APP_NAME="${APP_NAME:-finance-genie-analyst-client}"
WORKSPACE_SOURCE_PATH="${WORKSPACE_SOURCE_PATH:-}"
TMP_DIR="$(mktemp -d -t analyst-client-deploy.XXXXXX)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

if ! command -v databricks >/dev/null 2>&1; then
  echo "databricks CLI is required. Install and authenticate it first." >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to prepare the deployment source directory." >&2
  exit 1
fi

DBX=(databricks)
if [[ -n "${DATABRICKS_CONFIG_PROFILE:-}" ]]; then
  DBX+=(--profile "${DATABRICKS_CONFIG_PROFILE}")
fi

if [[ -z "${WORKSPACE_SOURCE_PATH}" ]]; then
  USER_JSON="$("${DBX[@]}" current-user me --output json)"
  USER_NAME="$(printf '%s' "${USER_JSON}" | python -c 'import json, sys; print(json.load(sys.stdin)["userName"])')"
  WORKSPACE_SOURCE_PATH="/Workspace/Users/${USER_NAME}/apps/${APP_NAME}"
fi

echo "Preparing app source"
rsync -a \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".env" \
  --exclude ".env.local" \
  --exclude ".venv/" \
  --exclude ".pytest_cache/" \
  --exclude "test-results/" \
  --exclude ".DS_Store" \
  "${APP_DIR}/" "${TMP_DIR}/"

echo "Using app name: ${APP_NAME}"
echo "Workspace source: ${WORKSPACE_SOURCE_PATH}"

if "${DBX[@]}" apps get "${APP_NAME}" >/dev/null 2>&1; then
  echo "App already exists"
else
  echo "Creating Databricks App"
  "${DBX[@]}" apps create "${APP_NAME}"
fi

echo "Uploading source to workspace"
if "${DBX[@]}" workspace get-status "${WORKSPACE_SOURCE_PATH}" >/dev/null 2>&1; then
  echo "Clearing existing workspace source path"
  "${DBX[@]}" workspace delete "${WORKSPACE_SOURCE_PATH}" --recursive
fi
"${DBX[@]}" workspace mkdirs "${WORKSPACE_SOURCE_PATH}"
"${DBX[@]}" workspace import-dir "${TMP_DIR}" "${WORKSPACE_SOURCE_PATH}" --overwrite

echo "Deploying app"
"${DBX[@]}" apps deploy "${APP_NAME}" --source-code-path "${WORKSPACE_SOURCE_PATH}"

echo
echo "Deployment submitted. App details:"
"${DBX[@]}" apps get "${APP_NAME}"
