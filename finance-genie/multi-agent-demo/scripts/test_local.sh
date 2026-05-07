#!/usr/bin/env bash
# Run local validation for the graph-specialist project.
#
# Usage:
#   ./scripts/test_local.sh [--agent-smoke]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-${DEMO_DIR}/.uv-cache}"
AGENT_SMOKE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-smoke)
      AGENT_SMOKE=1
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

echo "==> Bash syntax checks"
bash -n setup_secrets.sh
for script in scripts/*.sh; do
  bash -n "$script"
done

echo
echo "==> Python syntax checks"
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  config.py \
  finance_graph_supervisor_agent.py \
  cli/__init__.py \
  cli/__main__.py \
  jobs/00_validate_demo_preconditions.py \
  jobs/01_deploy_agent.py \
  jobs/02_validate_endpoint.py \
  setup/provision_connection.py \
  validation/validate_endpoint.py \
  validation/query_endpoint.py \
  validation/delete_endpoint.py \
  scripts/local_agent_smoke.py \
  scripts/local_agent_server.py

if [[ "$AGENT_SMOKE" -eq 1 ]]; then
  echo
  echo "==> Local in-process agent smoke test"
  uv run python scripts/local_agent_smoke.py
fi

find "$DEMO_DIR" -maxdepth 2 -type d -name '__pycache__' -prune -exec rm -rf {} +

echo
echo "Local validation complete."
