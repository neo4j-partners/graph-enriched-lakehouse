#!/bin/bash
#
# Setup Databricks secrets for the Agentic Commerce agent
# Reads credentials from .env and creates secrets in Databricks
#
# Usage:
#   1. Copy .env.sample to .env and fill in your credentials
#   2. Run: ./scripts/setup_secrets.sh <profile> [scope-name]
#      Examples:
#        ./scripts/setup_secrets.sh DEFAULT                  # Uses default scope: retail-agent-secrets
#        ./scripts/setup_secrets.sh my-profile               # Custom profile, default scope
#        ./scripts/setup_secrets.sh my-profile my-scope      # Custom profile and scope
#
# Mapping (.env → Databricks secret):
#   NEO4J_URI      → neo4j-uri
#   NEO4J_PASSWORD → neo4j-password

set -e

# Databricks profile (required)
if [[ -z "$1" ]]; then
    echo "Usage: ./scripts/setup_secrets.sh <profile> [scope-name]"
    echo "  profile:    Databricks CLI profile (e.g. DEFAULT, my-workspace)"
    echo "  scope-name: Secret scope (default: retail-agent-secrets)"
    exit 1
fi

PROFILE="$1"
SCOPE_NAME="${2:-retail-agent-secrets}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

# Pass --profile to all databricks CLI commands
DBX="databricks --profile $PROFILE"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

log_info "Using profile: $PROFILE"
log_info "Using secret scope: $SCOPE_NAME"

# Check for .env file
if [[ ! -f "$ENV_FILE" ]]; then
    log_error ".env file not found"
    echo "Copy .env.sample to .env and fill in your credentials:"
    echo "  cp .env.sample .env"
    exit 1
fi

# Check for databricks CLI
if ! command -v databricks &> /dev/null; then
    log_error "Databricks CLI not found"
    echo "Install with: pip install databricks-cli"
    echo "Or: brew install databricks"
    echo ""
    echo "Then configure with: databricks auth login"
    exit 1
fi

# Load .env file
log_info "Loading credentials from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a

# Validate required variables
missing=()
[[ -z "$NEO4J_URI" ]] && missing+=("NEO4J_URI")
[[ -z "$NEO4J_PASSWORD" ]] && missing+=("NEO4J_PASSWORD")

if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing required variables in .env: ${missing[*]}"
    exit 1
fi

# Create secret scope (ignore error if already exists)
log_info "Creating secret scope: $SCOPE_NAME"
if $DBX secrets create-scope "$SCOPE_NAME" 2>/dev/null; then
    log_info "Secret scope created"
else
    log_warn "Secret scope already exists (or failed to create)"
fi

# Function to set a secret
set_secret() {
    local key=$1
    local value=$2
    log_info "Setting secret: $key"
    echo -n "$value" | $DBX secrets put-secret "$SCOPE_NAME" "$key"
}

# Set required secrets
set_secret "neo4j-uri" "$NEO4J_URI"
set_secret "neo4j-password" "$NEO4J_PASSWORD"

log_info "Done! Secrets configured in scope: $SCOPE_NAME"
echo ""

# List secrets to confirm
log_info "Validating secrets..."
echo ""
echo "Secrets in scope '$SCOPE_NAME':"
$DBX secrets list-secrets "$SCOPE_NAME"
echo ""

echo "Use in Databricks notebooks:"
echo "  neo4j_uri  = dbutils.secrets.get(\"$SCOPE_NAME\", \"neo4j-uri\")"
echo "  neo4j_pass = dbutils.secrets.get(\"$SCOPE_NAME\", \"neo4j-password\")"
echo ""
echo "Model Serving env vars (set automatically by deploy.py):"
echo "  NEO4J_URI      → {{secrets/$SCOPE_NAME/neo4j-uri}}"
echo "  NEO4J_PASSWORD → {{secrets/$SCOPE_NAME/neo4j-password}}"
echo ""
