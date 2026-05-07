#!/usr/bin/env bash
# Deploy the simple-finance-agnet end to end.
#
# Usage:
#   ./scripts/deploy_all.sh [--profile NAME] [--compute cluster|serverless]
#                           [--skip-local-test] [--skip-smoke-test]
#                           [--endpoint-timeout-min MINUTES]
#
# Prerequisite:
#   Run finance-genie/neo4j-mcp-demo/deploy.sh first to create and validate the
#   Neo4j MCP Unity Catalog connection referenced by UC_CONNECTION_NAME.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DEMO_DIR}/.env"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"

PROFILE=""
COMPUTE=""
SKIP_LOCAL_TEST=0
SKIP_SMOKE_TEST=0
ENDPOINT_TIMEOUT_MIN=30
CURRENT_STEP=""

fail() {
  echo "Error: $*" >&2
  exit 1
}

on_error() {
  local status=$?
  echo >&2
  echo "FAILED: ${CURRENT_STEP:-deploy_all} (exit ${status})" >&2
  exit "$status"
}
trap on_error ERR

run_step() {
  CURRENT_STEP="$1"
  shift
  echo
  echo "==> ${CURRENT_STEP}"
  "$@"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      [[ $# -ge 2 ]] || fail "--profile requires a value"
      PROFILE="$2"
      shift 2
      ;;
    --compute)
      [[ $# -ge 2 ]] || fail "--compute requires cluster or serverless"
      case "$2" in
        cluster|serverless) COMPUTE="$2" ;;
        *) fail "--compute must be cluster or serverless" ;;
      esac
      shift 2
      ;;
    --skip-local-test)
      SKIP_LOCAL_TEST=1
      shift
      ;;
    --skip-smoke-test)
      SKIP_SMOKE_TEST=1
      shift
      ;;
    --endpoint-timeout-min)
      [[ $# -ge 2 ]] || fail "--endpoint-timeout-min requires a value"
      [[ "$2" =~ ^[0-9]+$ ]] || fail "--endpoint-timeout-min must be an integer"
      ENDPOINT_TIMEOUT_MIN="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ -f "$ENV_FILE" ]] || fail "${ENV_FILE} not found. Copy .env.sample to .env first."
command -v uv >/dev/null 2>&1 || fail "uv not found. Install uv before running deploy."

cd "$DEMO_DIR"

PROFILE_ARGS=()
if [[ -n "$PROFILE" ]]; then
  PROFILE_ARGS=(--profile "$PROFILE")
  export DATABRICKS_PROFILE="$PROFILE"
fi

COMPUTE_ARGS=()
if [[ -n "$COMPUTE" ]]; then
  export DATABRICKS_COMPUTE_MODE="$COMPUTE"
  COMPUTE_ARGS=(--compute "$COMPUTE")
fi

if [[ "$SKIP_LOCAL_TEST" -eq 0 ]]; then
  run_step "Run local static validation" \
    ./scripts/test_local.sh
fi

run_step "Upload Databricks job scripts and agent code" \
  uv run python -m cli upload --all

run_step "Run remote MCP precondition validation" \
  uv run python -m cli submit ${COMPUTE_ARGS[@]+"${COMPUTE_ARGS[@]}"} 00_validate_demo_preconditions.py

run_step "Deploy simple-finance-agnet Model Serving endpoint" \
  uv run python -m cli submit ${COMPUTE_ARGS[@]+"${COMPUTE_ARGS[@]}"} 01_deploy_agent.py

CURRENT_STEP="Wait for serving endpoint readiness"
echo
echo "==> ${CURRENT_STEP}"
deadline=$((SECONDS + ENDPOINT_TIMEOUT_MIN * 60))
while true; do
  if uv run validation/validate_endpoint.py ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}; then
    break
  fi
  if (( SECONDS >= deadline )); then
    fail "endpoint did not become READY within ${ENDPOINT_TIMEOUT_MIN} minutes"
  fi
  echo "Endpoint is not READY yet; retrying in 60 seconds..."
  sleep 60
done

if [[ "$SKIP_SMOKE_TEST" -eq 0 ]]; then
  run_step "Run remote endpoint smoke test as a Databricks job" \
    uv run python -m cli submit ${COMPUTE_ARGS[@]+"${COMPUTE_ARGS[@]}"} 02_validate_endpoint.py

  run_step "Run local SDK query against remote endpoint" \
    ./scripts/test_remote.sh ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}
fi

echo
echo "Deployment complete."
