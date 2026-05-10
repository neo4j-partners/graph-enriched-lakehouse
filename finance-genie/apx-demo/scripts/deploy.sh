#!/usr/bin/env bash
#
# deploy.sh: deploy the fraud-analyst bundle to Databricks.
#
# Reads .env (alongside this script's app root) for:
#   DATABRICKS_PROFILE             ~/.databrickscfg profile name
#   FRAUD_ANALYST_WAREHOUSE_ID     SQL warehouse the app queries
#   FRAUD_ANALYST_GENIE_SPACE_ID   Genie Space the app calls
#
# Usage:
#   scripts/deploy.sh           deploy and exit
#   scripts/deploy.sh --log     deploy, then tail app logs until you ctrl-c
#   scripts/deploy.sh -h        show this help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${APP_DIR}/.env"

show_help() {
  awk '/^[^#]/{exit} NR>2{sub(/^# ?/,""); print}' "${BASH_SOURCE[0]}"
  exit 0
}

case "${1:-}" in
  -h|--help) show_help ;;
esac

LOG_AFTER_DEPLOY=false
if [[ "${1:-}" == "--log" ]]; then
  LOG_AFTER_DEPLOY=true
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "❌ Missing ${ENV_FILE}"
  echo "   cp ${APP_DIR}/.env.sample ${ENV_FILE} and fill in values."
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

: "${DATABRICKS_PROFILE:?DATABRICKS_PROFILE must be set in .env}"
: "${FRAUD_ANALYST_WAREHOUSE_ID:?FRAUD_ANALYST_WAREHOUSE_ID must be set in .env}"
: "${FRAUD_ANALYST_GENIE_SPACE_ID:?FRAUD_ANALYST_GENIE_SPACE_ID must be set in .env}"

APP_NAME="fraud-analyst"

echo "── fraud-analyst deploy ─────────────────────────────────────────"
echo "  profile        : ${DATABRICKS_PROFILE}"
echo "  warehouse_id   : ${FRAUD_ANALYST_WAREHOUSE_ID}"
echo "  genie_space_id : ${FRAUD_ANALYST_GENIE_SPACE_ID}"
echo "  catalog        : ${FRAUD_ANALYST_CATALOG:-graph-enriched-lakehouse}"
echo "  schema         : ${FRAUD_ANALYST_SCHEMA:-graph-enriched-schema}"
echo "──────────────────────────────────────────────────────────────────"

cd "${APP_DIR}"

databricks bundle deploy \
  --profile "${DATABRICKS_PROFILE}" \
  --var "warehouse_id=${FRAUD_ANALYST_WAREHOUSE_ID}" \
  --var "genie_space_id=${FRAUD_ANALYST_GENIE_SPACE_ID}"

echo ""
echo "✅ Bundle deployed."

if [[ "${LOG_AFTER_DEPLOY}" == "true" ]]; then
  echo ""
  echo "📜 Tailing logs for app '${APP_NAME}' (ctrl-c to stop)…"
  echo ""
  databricks apps logs "${APP_NAME}" --profile "${DATABRICKS_PROFILE}" --follow
fi
