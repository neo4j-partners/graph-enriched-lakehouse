#!/usr/bin/env bash
# upload_and_create_tables.sh
#
# 1. Uploads CSVs from finance-genie/data/ to a Unity Catalog Volume via the Databricks CLI
# 2. Creates managed Delta tables in the same catalog/schema from those CSVs
#
# Usage:
#   export DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
#   ./upload_and_create_tables.sh
#
# Optional overrides:
#   DATABRICKS_PROFILE   (default: azure-rk-knight)
#   DATABRICKS_CATALOG   (default: graph-enriched-lakehouse)
#   DATABRICKS_SCHEMA    (default: graph-enriched-schema)
#   DATABRICKS_VOLUME    (default: graph-enriched-volume)

set -euo pipefail

# ── Load .env if present ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  set -o allexport
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/.env"
  set +o allexport
fi

# ── Configuration ─────────────────────────────────────────────────────────────
PROFILE="${DATABRICKS_PROFILE:-azure-rk-knight}"
CATALOG="${DATABRICKS_CATALOG:-graph-enriched-lakehouse}"
SCHEMA="${DATABRICKS_SCHEMA:-graph-enriched-schema}"
VOLUME="${DATABRICKS_VOLUME:-graph-enriched-volume}"
VOLUME_PATH="/Volumes/${CATALOG}/${SCHEMA}/${VOLUME}"

if [[ -z "${DATABRICKS_WAREHOUSE_ID:-}" ]]; then
  echo "Error: DATABRICKS_WAREHOUSE_ID is not set." >&2
  echo "Find your warehouse ID in Databricks under SQL Warehouses → <warehouse> → Connection Details." >&2
  exit 1
fi

DATA_DIR="${SCRIPT_DIR}/../data"
CLI="databricks --profile ${PROFILE}"

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
ok()   { echo "[$(date '+%H:%M:%S')]   ✓ $*"; }
err()  { echo "[$(date '+%H:%M:%S')]   ✗ $*" >&2; }

# Execute a SQL statement via the Databricks SQL Statements REST API.
# Uses a temp file to safely handle multi-line SQL and special characters.
run_sql() {
  local label="$1"
  local sql="$2"
  log "SQL: ${label}"

  local tmpfile
  tmpfile=$(mktemp /tmp/dbr_sql_XXXXX)
  trap 'rm -f "$tmpfile"' RETURN

  # Build the JSON payload with Python to handle all escaping correctly
  python3 - "$DATABRICKS_WAREHOUSE_ID" "$sql" <<'PYEOF' > "$tmpfile"
import json, sys
print(json.dumps({
    "warehouse_id":   sys.argv[1],
    "statement":      sys.argv[2],
    "wait_timeout":   "50s",
    "on_wait_timeout": "CANCEL"
}))
PYEOF

  local result state
  result=$($CLI api post /api/2.0/sql/statements --json @"$tmpfile")
  state=$(echo "$result" | python3 -c \
    'import json,sys; print(json.load(sys.stdin).get("status",{}).get("state","UNKNOWN"))')

  if [[ "$state" != "SUCCEEDED" ]]; then
    local detail
    detail=$(echo "$result" | python3 -c \
      'import json,sys; d=json.load(sys.stdin); e=d.get("status",{}).get("error",{}); print(e)' 2>/dev/null || true)
    err "${label} failed (state=${state}): ${detail}"
    exit 1
  fi
  ok "${label}"
}

# ── Step 1: Bootstrap schema / volume ────────────────────────────────────────
# Catalog 'graph-enriched-lakehouse' is pre-existing; only create schema/volume.
log "=== Step 1: Bootstrapping schema / volume ==="

run_sql "CREATE SCHEMA IF NOT EXISTS" \
  "CREATE SCHEMA IF NOT EXISTS \`${CATALOG}\`.\`${SCHEMA}\`"

run_sql "CREATE VOLUME IF NOT EXISTS" \
  "CREATE VOLUME IF NOT EXISTS \`${CATALOG}\`.\`${SCHEMA}\`.\`${VOLUME}\`"

# ── Step 2: Upload CSVs to Volume ─────────────────────────────────────────────
log ""
log "=== Step 2: Uploading CSVs → ${VOLUME_PATH} ==="

if [[ ! -d "$DATA_DIR" ]]; then
  err "Data directory not found: ${DATA_DIR}"
  exit 1
fi

for csv_file in "${DATA_DIR}"/*.csv; do
  [[ -f "$csv_file" ]] || { err "No CSV files found in ${DATA_DIR}"; exit 1; }
  filename=$(basename "$csv_file")
  log "  Uploading ${filename}…"
  $CLI fs cp "$csv_file" "dbfs:${VOLUME_PATH}/${filename}" --overwrite
  ok "${filename} → ${VOLUME_PATH}/${filename}"
done

# ── Step 3: Create Delta tables from Volume CSVs ──────────────────────────────
log ""
log "=== Step 3: Creating Delta tables in \`${CATALOG}\`.\`${SCHEMA}\` ==="

# accounts — one row per account holder
run_sql "CREATE TABLE accounts" \
  "CREATE OR REPLACE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.accounts
   USING DELTA
   COMMENT 'Account dimension — one row per account holder'
   AS
   SELECT
     CAST(account_id   AS BIGINT)  AS account_id,
     account_hash,
     account_type,
     region,
     CAST(balance      AS DOUBLE)  AS balance,
     CAST(opened_date  AS DATE)    AS opened_date,
     CAST(holder_age   AS INT)     AS holder_age
   FROM read_files(
     '${VOLUME_PATH}/accounts.csv',
     format      => 'csv',
     header      => 'true',
     inferSchema => 'false',
     schema      => 'account_id STRING, account_hash STRING, account_type STRING, region STRING, balance STRING, opened_date STRING, holder_age STRING'
   )"

# merchants — merchant dimension with risk tier
run_sql "CREATE TABLE merchants" \
  "CREATE OR REPLACE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.merchants
   USING DELTA
   COMMENT 'Merchant dimension with risk tier classification'
   AS
   SELECT
     CAST(merchant_id AS BIGINT) AS merchant_id,
     merchant_name,
     category,
     risk_tier,
     region
   FROM read_files(
     '${VOLUME_PATH}/merchants.csv',
     format      => 'csv',
     header      => 'true',
     inferSchema => 'false',
     schema      => 'merchant_id STRING, merchant_name STRING, category STRING, risk_tier STRING, region STRING'
   )"

# transactions — fact table of payments
run_sql "CREATE TABLE transactions" \
  "CREATE OR REPLACE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.transactions
   USING DELTA
   COMMENT 'Transaction fact table — one row per payment event'
   AS
   SELECT
     CAST(txn_id        AS BIGINT)    AS txn_id,
     CAST(account_id    AS BIGINT)    AS account_id,
     CAST(merchant_id   AS BIGINT)    AS merchant_id,
     CAST(amount        AS DOUBLE)    AS amount,
     CAST(txn_timestamp AS TIMESTAMP) AS txn_timestamp,
     CAST(txn_hour      AS INT)       AS txn_hour
   FROM read_files(
     '${VOLUME_PATH}/transactions.csv',
     format      => 'csv',
     header      => 'true',
     inferSchema => 'false',
     schema      => 'txn_id STRING, account_id STRING, merchant_id STRING, amount STRING, txn_timestamp STRING, txn_hour STRING'
   )"

# account_links — directed graph edges (account-to-account transfers)
run_sql "CREATE TABLE account_links" \
  "CREATE OR REPLACE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.account_links
   USING DELTA
   COMMENT 'Account-to-account transfer graph edges'
   AS
   SELECT
     CAST(link_id            AS BIGINT)    AS link_id,
     CAST(src_account_id     AS BIGINT)    AS src_account_id,
     CAST(dst_account_id     AS BIGINT)    AS dst_account_id,
     CAST(amount             AS DOUBLE)    AS amount,
     CAST(transfer_timestamp AS TIMESTAMP) AS transfer_timestamp
   FROM read_files(
     '${VOLUME_PATH}/account_links.csv',
     format      => 'csv',
     header      => 'true',
     inferSchema => 'false',
     schema      => 'link_id STRING, src_account_id STRING, dst_account_id STRING, amount STRING, transfer_timestamp STRING'
   )"

# account_labels — fraud ground-truth labels
run_sql "CREATE TABLE account_labels" \
  "CREATE OR REPLACE TABLE \`${CATALOG}\`.\`${SCHEMA}\`.account_labels
   USING DELTA
   COMMENT 'Fraud ground-truth labels — one row per account'
   AS
   SELECT
     CAST(account_id AS BIGINT)  AS account_id,
     CAST(
       CASE WHEN lower(is_fraud) = 'true' THEN 'true' ELSE 'false' END
       AS BOOLEAN
     ) AS is_fraud
   FROM read_files(
     '${VOLUME_PATH}/account_labels.csv',
     format      => 'csv',
     header      => 'true',
     inferSchema => 'false',
     schema      => 'account_id STRING, is_fraud STRING'
   )"

# ── Done ──────────────────────────────────────────────────────────────────────
log ""
log "=== All done! ==="
log "Volume:  ${VOLUME_PATH}"
log "Tables:"
log "  \`${CATALOG}\`.\`${SCHEMA}\`.accounts"
log "  \`${CATALOG}\`.\`${SCHEMA}\`.merchants"
log "  \`${CATALOG}\`.\`${SCHEMA}\`.transactions"
log "  \`${CATALOG}\`.\`${SCHEMA}\`.account_links"
log "  \`${CATALOG}\`.\`${SCHEMA}\`.account_labels"
