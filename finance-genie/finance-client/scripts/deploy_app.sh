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

APP_NAME="${APP_NAME:-finance-genie-client}"
WORKSPACE_SOURCE_PATH="${WORKSPACE_SOURCE_PATH:-}"
MCP_SCHEMA_CONNECTION_NAME="${MCP_SCHEMA_CONNECTION_NAME:-neo4j_agentcore_mcp}"
GRANT_APP_SP_MCP_CONNECTION_ACCESS="${GRANT_APP_SP_MCP_CONNECTION_ACCESS:-true}"
TMP_DIR="$(mktemp -d -t finance-genie-client-deploy.XXXXXX)"

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

APP_SP_CLIENT_ID=""

get_app_sp_client_id() {
  if [[ -z "${APP_SP_CLIENT_ID}" ]]; then
    APP_JSON="$("${DBX[@]}" apps get "${APP_NAME}" --output json)"
    APP_SP_CLIENT_ID="$(printf '%s' "${APP_JSON}" | python -c 'import json, sys; print(json.load(sys.stdin)["service_principal_client_id"])')"
  fi
  printf '%s' "${APP_SP_CLIENT_ID}"
}

echo "Preparing app source"
rsync -a \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".env.local" \
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

if [[ -n "${DATABRICKS_WAREHOUSE_ID:-}" ]]; then
  echo "Binding SQL warehouse resource: sql-warehouse"
  RESOURCE_JSON="$(printf '{"update_mask":"resources","app":{"resources":[{"name":"sql-warehouse","sql_warehouse":{"id":"%s","permission":"CAN_USE"}}]}}' "${DATABRICKS_WAREHOUSE_ID}")"
  "${DBX[@]}" apps create-update "${APP_NAME}" --json "${RESOURCE_JSON}" >/dev/null
else
  echo "Skipping SQL warehouse resource binding because DATABRICKS_WAREHOUSE_ID is not set"
fi

if [[ "${GRANT_APP_SP_SCHEMA_ACCESS:-false}" == "true" ]]; then
  if [[ -z "${CATALOG:-}" || -z "${SCHEMA:-}" ]]; then
    echo "GRANT_APP_SP_SCHEMA_ACCESS=true requires CATALOG and SCHEMA." >&2
    exit 1
  fi
  APP_SP_CLIENT_ID="$(get_app_sp_client_id)"

  echo "Granting app service principal read access to ${CATALOG}.${SCHEMA}"
  CATALOG_GRANT_JSON="$(printf '{"changes":[{"principal":"%s","add":["USE_CATALOG"]}]}' "${APP_SP_CLIENT_ID}")"
  SCHEMA_GRANT_JSON="$(printf '{"changes":[{"principal":"%s","add":["USE_SCHEMA","SELECT"]}]}' "${APP_SP_CLIENT_ID}")"
  "${DBX[@]}" grants update catalog "${CATALOG}" --json "${CATALOG_GRANT_JSON}" >/dev/null
  "${DBX[@]}" grants update schema "${CATALOG}.${SCHEMA}" --json "${SCHEMA_GRANT_JSON}" >/dev/null
fi

if [[ "${GRANT_APP_SP_MCP_CONNECTION_ACCESS}" == "true" ]]; then
  if [[ -z "${MCP_SCHEMA_CONNECTION_NAME}" ]]; then
    echo "GRANT_APP_SP_MCP_CONNECTION_ACCESS=true requires MCP_SCHEMA_CONNECTION_NAME." >&2
    exit 1
  fi
  APP_SP_CLIENT_ID="$(get_app_sp_client_id)"

  echo "Granting app service principal USE CONNECTION on ${MCP_SCHEMA_CONNECTION_NAME}"
  CONNECTION_GRANT_JSON="$(printf '{"changes":[{"principal":"%s","add":["USE CONNECTION"]}]}' "${APP_SP_CLIENT_ID}")"
  "${DBX[@]}" grants update connection "${MCP_SCHEMA_CONNECTION_NAME}" --json "${CONNECTION_GRANT_JSON}" >/dev/null
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

echo
echo "The app reads the sql-warehouse resource through DATABRICKS_WAREHOUSE_ID valueFrom in app.yaml."
echo "Set GRANT_APP_SP_SCHEMA_ACCESS=true to have this script grant read access on CATALOG.SCHEMA."
echo "Set GRANT_APP_SP_MCP_CONNECTION_ACCESS=false to skip granting USE CONNECTION on ${MCP_SCHEMA_CONNECTION_NAME}."
