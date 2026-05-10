#!/usr/bin/env bash
# Provisions finance-genie Databricks secret scopes from the root .env file.
#
# Usage:
#   ./setup_secrets.sh [--profile NAME] [ENV_FILE]
#
# ENV_FILE defaults to finance-genie/.env. This script intentionally provisions
# separate scopes for separate runtime surfaces, while using one root env file
# as the operator-facing source of truth.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
PROFILE="${DATABRICKS_CONFIG_PROFILE:-${DATABRICKS_PROFILE:-}}"

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      PROFILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      ENV_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
      shift
      ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: $ENV_FILE not found." >&2
  echo "Copy .env.sample to .env at the finance-genie root and fill in values." >&2
  exit 1
fi

if ! command -v databricks >/dev/null 2>&1; then
  echo "Error: databricks CLI not found." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PROFILE="${PROFILE:-${DATABRICKS_CONFIG_PROFILE:-${DATABRICKS_PROFILE:-}}}"
if [[ -z "$PROFILE" ]]; then
  echo "Available Databricks profiles:"
  databricks auth profiles 2>/dev/null || echo "  (could not list profiles; check ~/.databrickscfg)"
  echo
  read -r -p "Profile name [DEFAULT]: " PROFILE
  PROFILE="${PROFILE:-DEFAULT}"
fi

export DATABRICKS_CONFIG_PROFILE="$PROFILE"
echo "Using Databricks profile: $DATABRICKS_CONFIG_PROFILE"

: "${NEO4J_URI:?NEO4J_URI is not set in $ENV_FILE}"
: "${NEO4J_USERNAME:?NEO4J_USERNAME is not set in $ENV_FILE}"
: "${NEO4J_PASSWORD:?NEO4J_PASSWORD is not set in $ENV_FILE}"
: "${GENIE_SPACE_ID_BEFORE:?GENIE_SPACE_ID_BEFORE is not set in $ENV_FILE}"
: "${GENIE_SPACE_ID_AFTER:?GENIE_SPACE_ID_AFTER is not set in $ENV_FILE}"

NEO4J_SECRET_SCOPE="${NEO4J_SECRET_SCOPE:-neo4j-graph-engineering}"
ANALYST_CLIENT_SECRET_SCOPE="${ANALYST_CLIENT_SECRET_SCOPE:-finance-genie-analyst-client}"
GENIE_SPACE_ID="${GENIE_SPACE_ID:-$GENIE_SPACE_ID_AFTER}"

ensure_scope() {
  local scope="$1"
  set +e
  local output
  output="$(databricks secrets create-scope "$scope" 2>&1)"
  local rc=$?
  set -e

  if [[ "$rc" -eq 0 ]]; then
    echo "Created secret scope: $scope"
  elif [[ "$output" == *"already exists"* ]]; then
    echo "Secret scope already exists: $scope"
  else
    echo "Error creating scope $scope: $output" >&2
    exit 1
  fi
}

put_secret() {
  local scope="$1"
  local key="$2"
  local value="$3"
  printf '  - %s/%s\n' "$scope" "$key"
  databricks secrets put-secret "$scope" "$key" --string-value "$value"
}

echo
echo "Writing automated/workshop Neo4j and Genie secrets"
ensure_scope "$NEO4J_SECRET_SCOPE"
put_secret "$NEO4J_SECRET_SCOPE" "uri" "$NEO4J_URI"
put_secret "$NEO4J_SECRET_SCOPE" "username" "$NEO4J_USERNAME"
put_secret "$NEO4J_SECRET_SCOPE" "password" "$NEO4J_PASSWORD"
put_secret "$NEO4J_SECRET_SCOPE" "genie_space_id_before" "$GENIE_SPACE_ID_BEFORE"
put_secret "$NEO4J_SECRET_SCOPE" "genie_space_id_after" "$GENIE_SPACE_ID_AFTER"
put_secret "$NEO4J_SECRET_SCOPE" "genie_space_id" "$GENIE_SPACE_ID_BEFORE"

echo
echo "Writing analyst-client real-backend secrets"
ensure_scope "$ANALYST_CLIENT_SECRET_SCOPE"
put_secret "$ANALYST_CLIENT_SECRET_SCOPE" "neo4j_uri" "$NEO4J_URI"
put_secret "$ANALYST_CLIENT_SECRET_SCOPE" "neo4j_username" "$NEO4J_USERNAME"
put_secret "$ANALYST_CLIENT_SECRET_SCOPE" "neo4j_password" "$NEO4J_PASSWORD"
put_secret "$ANALYST_CLIENT_SECRET_SCOPE" "genie_space_id" "$GENIE_SPACE_ID"

store_agentcore_secrets() {
  local credentials_path="${AGENTCORE_CREDENTIALS_PATH:-}"
  local scope="${MCP_SECRET_SCOPE:-mcp-neo4j-secrets}"
  if [[ -z "$credentials_path" ]]; then
    return
  fi
  if [[ "$credentials_path" != /* ]]; then
    credentials_path="${ROOT_DIR}/${credentials_path}"
  fi
  if [[ ! -f "$credentials_path" ]]; then
    echo
    echo "Skipping MCP OAuth secrets; credential file not found: $credentials_path"
    return
  fi

  echo
  echo "Writing MCP OAuth secrets"
  ensure_scope "$scope"
  while IFS=$'\t' read -r key value; do
    put_secret "$scope" "$key" "$value"
  done < <(python3 - "$credentials_path" <<'PY'
import json
import sys
from urllib.parse import urlparse

path = sys.argv[1]
data = json.load(open(path, encoding="utf-8"))
gateway_url = data["gateway_url"]
host = f"{urlparse(gateway_url).scheme}://{urlparse(gateway_url).netloc}"
items = {
    "gateway_host": host,
    "client_id": data["client_id"],
    "client_secret": data["client_secret"],
    "token_endpoint": data["token_url"],
    "oauth_scope": data["scope"],
}
for key, value in items.items():
    print(f"{key}\t{value}")
PY
)
}

store_agentcore_secrets

echo
echo "Done."
