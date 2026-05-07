#!/usr/bin/env bash
# Stop remote serving costs by deleting the simple-finance-agnet serving endpoint.
#
# Usage:
#   ./scripts/stop_remote.sh [--profile NAME] --yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"
ENV_FILE="${DEMO_DIR}/.env"
PROFILE=""
YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      [[ $# -ge 2 ]] || { echo "Error: --profile requires a value" >&2; exit 1; }
      PROFILE="$2"
      shift 2
      ;;
    --yes)
      YES=1
      shift
      ;;
    -h|--help)
      sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
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

DELETE_ARGS=("${PROFILE_ARGS[@]}")
if [[ "$YES" -eq 1 ]]; then
  DELETE_ARGS+=(--yes)
fi

uv run validation/delete_endpoint.py ${DELETE_ARGS[@]+"${DELETE_ARGS[@]}"}
