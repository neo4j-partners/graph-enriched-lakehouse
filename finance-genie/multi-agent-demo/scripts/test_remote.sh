#!/usr/bin/env bash
# Validate and query the remote simple-finance-agnet serving endpoint.
#
# Usage:
#   ./scripts/test_remote.sh [--profile NAME] [--prompt TEXT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"
ENV_FILE="${DEMO_DIR}/../.env"
if [[ ! -f "$ENV_FILE" ]]; then
  ENV_FILE="${DEMO_DIR}/.env"
fi
PROFILE=""
PROMPT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--profile)
      [[ $# -ge 2 ]] || { echo "Error: --profile requires a value" >&2; exit 1; }
      PROFILE="$2"
      shift 2
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { echo "Error: --prompt requires a value" >&2; exit 1; }
      PROMPT="$2"
      shift 2
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
  echo "Error: ${ENV_FILE} not found. Copy ../.env.sample to ../.env first." >&2
  exit 1
}

PROFILE_ARGS=()
if [[ -n "$PROFILE" ]]; then
  PROFILE_ARGS=(--profile "$PROFILE")
  export DATABRICKS_PROFILE="$PROFILE"
fi

echo "==> Validate endpoint readiness"
uv run validation/validate_endpoint.py ${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}

echo
echo "==> Query endpoint"
QUERY_ARGS=("${PROFILE_ARGS[@]}")
if [[ -n "$PROMPT" ]]; then
  QUERY_ARGS+=(--prompt "$PROMPT")
fi
uv run validation/query_endpoint.py ${QUERY_ARGS[@]+"${QUERY_ARGS[@]}"}
