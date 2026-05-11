#!/usr/bin/env bash
# Compatibility wrapper. The shared finance-genie secret setup now lives at
# ../setup_secrets.sh and reads finance-genie/.env by default.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/../setup_secrets.sh" "$@"
