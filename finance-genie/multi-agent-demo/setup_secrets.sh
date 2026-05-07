#!/usr/bin/env bash
# Stores AgentCore OAuth credentials used by the Neo4j MCP Unity Catalog
# connection. The deployed graph specialist does not read these secrets
# directly; Databricks uses them through the UC HTTP connection named by
# UC_CONNECTION_NAME.
#
# Secrets written:
#   gateway_host    - scheme and host from .mcp-credentials.json gateway_url
#   client_id       - AgentCore OAuth client id
#   client_secret   - AgentCore OAuth client secret
#   token_endpoint  - AgentCore OAuth token URL
#   oauth_scope     - AgentCore OAuth scope
#
# Usage:
#   ./setup_secrets.sh [--profile NAME] [ENV_FILE]
#
# ENV_FILE defaults to multi-agent-demo/.env.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
PROFILE="${DATABRICKS_CONFIG_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      if [[ $# -lt 2 ]]; then
        echo "Error: --profile requires a value." >&2
        exit 1
      fi
      PROFILE="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
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
  echo "Copy .env.sample to .env and fill in your demo settings." >&2
  exit 1
fi

if ! command -v databricks >/dev/null 2>&1; then
  echo "Error: databricks CLI not found. Install the Databricks CLI first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

SCOPE="${MCP_SECRET_SCOPE:-mcp-neo4j-secrets}"
CREDENTIALS_PATH="${AGENTCORE_CREDENTIALS_PATH:-.mcp-credentials.json}"
if [[ "$CREDENTIALS_PATH" != /* ]]; then
  CREDENTIALS_PATH="${SCRIPT_DIR}/${CREDENTIALS_PATH}"
fi

if [[ ! -f "$CREDENTIALS_PATH" ]]; then
  echo "Error: credentials file not found: $CREDENTIALS_PATH" >&2
  echo "Copy the AgentCore-generated .mcp-credentials.json into this directory." >&2
  exit 1
fi

if [[ -z "$PROFILE" ]]; then
  echo "Available Databricks profiles:"
  databricks auth profiles 2>/dev/null || echo "  (could not list profiles; check ~/.databrickscfg)"
  echo
  read -r -p "Profile name [DEFAULT]: " PROFILE
  PROFILE="${PROFILE:-DEFAULT}"
fi

export DATABRICKS_CONFIG_PROFILE="$PROFILE"
echo "Using Databricks profile: $DATABRICKS_CONFIG_PROFILE"
echo

credential_value() {
  local field="$1"
  python3 -c '
import json
import sys
from urllib.parse import urlparse

path, field = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)

if field == "gateway_host":
    parsed = urlparse(data.get("gateway_url", ""))
    if not parsed.scheme or not parsed.netloc:
        raise SystemExit("gateway_url must be an absolute URL")
    print(f"{parsed.scheme}://{parsed.netloc}")
elif field == "token_endpoint":
    print(data.get("token_url", ""))
elif field == "oauth_scope":
    print(data.get("scope", ""))
else:
    print(data.get(field, ""))
' "$CREDENTIALS_PATH" "$field"
}

set +e
create_out=$(databricks secrets create-scope "$SCOPE" 2>&1)
create_rc=$?
set -e

if [[ "$create_rc" -eq 0 ]]; then
  echo "Created secret scope: $SCOPE"
elif [[ "$create_out" == *"already exists"* ]]; then
  echo "Secret scope already exists: $SCOPE"
else
  echo "Error creating scope: $create_out" >&2
  exit 1
fi

put_secret() {
  local key="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Error: credential field for $key is empty." >&2
    exit 1
  fi
  printf '  - %s\n' "$key"
  databricks secrets put-secret "$SCOPE" "$key" --string-value "$value"
}

echo "Writing Neo4j MCP connection secrets into $SCOPE:"
put_secret "gateway_host" "$(credential_value gateway_host)"
put_secret "client_id" "$(credential_value client_id)"
put_secret "client_secret" "$(credential_value client_secret)"
put_secret "token_endpoint" "$(credential_value token_endpoint)"
put_secret "oauth_scope" "$(credential_value oauth_scope)"

echo
echo "Done. The UC external MCP connection should reference secrets in scope:"
echo "  $SCOPE"
