#!/usr/bin/env bash
# Start or update the remote simple-finance-agnet Model Serving endpoint.
#
# Usage:
#   ./scripts/start_remote.sh [--profile NAME] [--compute cluster|serverless]
#                             [--endpoint-timeout-min MINUTES]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"
ENV_FILE="${DEMO_DIR}/.env"
PROFILE=""
COMPUTE=""
ENDPOINT_TIMEOUT_MIN=30

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      [[ $# -ge 2 ]] || { echo "Error: --profile requires a value" >&2; exit 1; }
      PROFILE="$2"
      shift 2
      ;;
    --compute)
      [[ $# -ge 2 ]] || { echo "Error: --compute requires cluster or serverless" >&2; exit 1; }
      case "$2" in
        cluster|serverless) COMPUTE="$2" ;;
        *) echo "Error: --compute must be cluster or serverless" >&2; exit 1 ;;
      esac
      shift 2
      ;;
    --endpoint-timeout-min)
      [[ $# -ge 2 ]] || { echo "Error: --endpoint-timeout-min requires a value" >&2; exit 1; }
      ENDPOINT_TIMEOUT_MIN="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$DEMO_DIR"

[[ -f "$ENV_FILE" ]] || {
  echo "Error: ${ENV_FILE} not found. Copy .env.sample to .env first." >&2
  exit 1
}

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

echo "==> Upload jobs and agent code"
uv run python -m cli upload --all

echo
echo "==> Validate remote MCP preconditions"
uv run python -m cli submit ${COMPUTE_ARGS[@]+"${COMPUTE_ARGS[@]}"} 00_validate_demo_preconditions.py

echo
echo "==> Deploy simple-finance-agnet endpoint"
uv run python -m cli submit ${COMPUTE_ARGS[@]+"${COMPUTE_ARGS[@]}"} 01_deploy_agent.py

echo
echo "==> Wait for endpoint readiness"
deadline=$((SECONDS + ENDPOINT_TIMEOUT_MIN * 60))
while true; do
  if uv run validation/validate_endpoint.py ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}; then
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "Error: endpoint did not become READY within ${ENDPOINT_TIMEOUT_MIN} minutes" >&2
    exit 1
  fi
  echo "Endpoint is not READY yet; retrying in 60 seconds..."
  sleep 60
done

echo
echo "Remote endpoint is ready."
