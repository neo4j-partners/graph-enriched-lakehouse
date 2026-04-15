#!/usr/bin/env bash
# Reads .env and pushes Neo4j Aura credentials into the Databricks secret
# scope "neo4j-graph-engineering". Requires the Databricks CLI to be
# installed and authenticated (databricks auth login or DATABRICKS_HOST/
# DATABRICKS_TOKEN env vars).
#
# Usage:
#   ./setup_secrets.sh [--profile NAME] [ENV_FILE]
#
# The Databricks profile is resolved once and exported as
# DATABRICKS_CONFIG_PROFILE so every subsequent CLI call in this script
# reuses it without re-prompting. Resolution order:
#   1. --profile / -p flag
#   2. DATABRICKS_CONFIG_PROFILE environment variable
#   3. Interactive prompt (lists available profiles)

set -euo pipefail

SCOPE="neo4j-graph-engineering"
ENV_FILE=".env"
PROFILE="${DATABRICKS_CONFIG_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      PROFILE="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--profile NAME] [ENV_FILE]"
      exit 0
      ;;
    *)
      ENV_FILE="$1"
      shift
      ;;
  esac
done

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found."
  echo "Copy .env.sample to .env and fill in your Neo4j Aura credentials."
  exit 1
fi

if ! command -v databricks >/dev/null 2>&1; then
  echo "Error: databricks CLI not found. Install from https://docs.databricks.com/dev-tools/cli/"
  exit 1
fi

# Resolve the Databricks profile once — every CLI call below inherits it via
# the exported DATABRICKS_CONFIG_PROFILE, so the user is never re-prompted.
if [ -z "$PROFILE" ]; then
  echo "Available Databricks profiles:"
  databricks auth profiles 2>/dev/null || echo "  (could not list profiles — check your ~/.databrickscfg)"
  echo
  read -r -p "Profile name [DEFAULT]: " PROFILE
  PROFILE="${PROFILE:-DEFAULT}"
fi

export DATABRICKS_CONFIG_PROFILE="$PROFILE"
echo "Using Databricks profile: $DATABRICKS_CONFIG_PROFILE"
echo

# Load .env
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${NEO4J_URI:?NEO4J_URI is not set in $ENV_FILE}"
: "${NEO4J_USERNAME:?NEO4J_USERNAME is not set in $ENV_FILE}"
: "${NEO4J_PASSWORD:?NEO4J_PASSWORD is not set in $ENV_FILE}"

# Create the scope — if it already exists, that is fine.
set +e
create_out=$(databricks secrets create-scope "$SCOPE" 2>&1)
create_rc=$?
set -e

if [ "$create_rc" -eq 0 ]; then
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
  printf '  - %s\n' "$key"
  databricks secrets put-secret "$SCOPE" "$key" --string-value "$value"
}

echo "Writing secrets into $SCOPE:"
put_secret "uri"      "$NEO4J_URI"
put_secret "username" "$NEO4J_USERNAME"
put_secret "password" "$NEO4J_PASSWORD"

echo
echo "Done. Notebooks can now read via:"
echo "  dbutils.secrets.get(\"$SCOPE\", \"uri\")"
