#!/usr/bin/env bash
# Run local validation for the simple finance agent project.
#
# Usage:
#   ./scripts/test_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

cd "$DEMO_DIR"

echo "==> Bash syntax checks"
for script in scripts/*.sh; do
  bash -n "$script"
done

echo
echo "==> Python syntax checks"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  config.py \
  simple_finance_agent.py \
  cli/__init__.py \
  cli/__main__.py \
  jobs/00_validate_demo_preconditions.py \
  jobs/01_deploy_agent.py \
  jobs/02_validate_endpoint.py \
  validation/validate_endpoint.py \
  validation/query_endpoint.py \
  validation/delete_endpoint.py

find "$DEMO_DIR" -maxdepth 2 -type d -name '__pycache__' -prune -exec rm -rf {} +

echo
echo "Local validation complete."
