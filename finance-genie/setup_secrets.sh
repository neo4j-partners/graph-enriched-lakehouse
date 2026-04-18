#!/usr/bin/env bash
# Reads .env files and pushes all credentials into the Databricks secret
# scope "neo4j-graph-engineering". Replaces the one-time manual setup in
# 00_required_setup.ipynb. Requires the Databricks CLI to be installed and
# authenticated (databricks auth login or DATABRICKS_HOST/DATABRICKS_TOKEN).
#
# Secrets written:
#   uri              — NEO4J_URI from .env (root)
#   username         — NEO4J_USERNAME from .env (root)
#   password         — NEO4J_PASSWORD from .env (root)
#   genie_space_id   — GENIE_SPACE_ID_BEFORE from accelerator/.env
#                      (read by hub_detection, community_structure,
#                       merchant_overlap demo notebooks)
#
# Usage:
#   ./setup_secrets.sh [--profile NAME] [ENV_FILE]
#
# ENV_FILE defaults to .env in the same directory as this script.
# accelerator/.env is always loaded from the sibling directory.
#
# The Databricks profile is resolved once and exported as
# DATABRICKS_CONFIG_PROFILE so every subsequent CLI call in this script
# reuses it without re-prompting. Resolution order:
#   1. --profile / -p flag
#   2. DATABRICKS_CONFIG_PROFILE environment variable
#   3. Interactive prompt (lists available profiles)

set -euo pipefail

SCOPE="neo4j-graph-engineering"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ACCELERATOR_ENV="${SCRIPT_DIR}/accelerator/.env"
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
      ENV_FILE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
      shift
      ;;
  esac
done

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found."
  echo "Copy .env.sample to .env and fill in your Neo4j Aura credentials."
  exit 1
fi

if [ ! -f "$ACCELERATOR_ENV" ]; then
  echo "Error: $ACCELERATOR_ENV not found."
  echo "Copy accelerator/.env.sample to accelerator/.env and fill in GENIE_SPACE_ID_BEFORE."
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

# Load root .env (Neo4j credentials)
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${NEO4J_URI:?NEO4J_URI is not set in $ENV_FILE}"
: "${NEO4J_USERNAME:?NEO4J_USERNAME is not set in $ENV_FILE}"
: "${NEO4J_PASSWORD:?NEO4J_PASSWORD is not set in $ENV_FILE}"

# Load accelerator/.env (Genie Space IDs) — only pick up GENIE_SPACE_ID_BEFORE
set -a
# shellcheck disable=SC1090
source "$ACCELERATOR_ENV"
set +a

: "${GENIE_SPACE_ID_BEFORE:?GENIE_SPACE_ID_BEFORE is not set in $ACCELERATOR_ENV}"

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
put_secret "uri"              "$NEO4J_URI"
put_secret "username"         "$NEO4J_USERNAME"
put_secret "password"         "$NEO4J_PASSWORD"
put_secret "genie_space_id"   "$GENIE_SPACE_ID_BEFORE"

echo
echo "Done. Notebooks can now read via:"
echo "  dbutils.secrets.get(\"$SCOPE\", \"uri\")"
echo "  dbutils.secrets.get(\"$SCOPE\", \"genie_space_id\")"
