#!/usr/bin/env python3
"""Create Delta Lake tables in Databricks Unity Catalog from generated CSVs.

This script:
1. Uploads CSV files from data/lakehouse/ to a Unity Catalog Volume.
2. Creates Delta Lake tables with proper types and partitioning.
3. Adds column comments for Genie compatibility.

Prerequisites:
- Databricks workspace with Unity Catalog enabled
- A SQL Warehouse running
- A Databricks CLI profile configured via: databricks configure --profile <name>
- Environment variables (in .env or exported):
    DATABRICKS_PROFILE  — CLI profile name (from ~/.databrickscfg)
    DATABRICKS_WAREHOUSE — SQL warehouse name
- Optional:
    DATABRICKS_CATALOG  (default: retail_assistant)
    DATABRICKS_SCHEMA   (default: retail)
    DATABRICKS_VOLUME   (default: retail_volume)
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "lakehouse"

# Load .env from project root
load_dotenv(DATA_DIR.parents[1] / ".env")

DATABRICKS_PROFILE = os.getenv("DATABRICKS_PROFILE")
DATABRICKS_WAREHOUSE = os.getenv("DATABRICKS_WAREHOUSE", "")
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "retail_assistant")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "retail")
DATABRICKS_VOLUME = os.getenv("DATABRICKS_VOLUME", "retail_volume")

VOLUME_PATH = f"/Volumes/{DATABRICKS_CATALOG}/{DATABRICKS_SCHEMA}/{DATABRICKS_VOLUME}"
FQN = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}"


CSV_FILES = [
    "transactions.csv",
    "customers.csv",
    "reviews.csv",
    "inventory_snapshots.csv",
    "stores.csv",
    "knowledge_articles.csv",
    "support_tickets.csv",
    "product_reviews.csv",
]


# ---------------------------------------------------------------------------
# Structured table definitions
# ---------------------------------------------------------------------------


class TableDef(BaseModel):
    """A Delta Lake table definition with its CREATE SQL and column comments."""

    name: str
    select_sql: str
    table_comment: str = ""
    comments: dict[str, str] = Field(default_factory=dict)


def _build_table_defs() -> list[TableDef]:
    """Build table definitions using runtime settings."""
    return [
        TableDef(
            name=f"{FQN}.transactions",
            select_sql=f"""
                SELECT
                    transaction_id, order_id, customer_id, product_id, product_name,
                    category, brand,
                    CAST(quantity AS INT) AS quantity,
                    CAST(unit_price AS DOUBLE) AS unit_price,
                    CAST(discount_pct AS DOUBLE) AS discount_pct,
                    CAST(total_price AS DOUBLE) AS total_price,
                    CAST(purchase_date AS TIMESTAMP) AS purchase_date,
                    CAST(purchase_hour AS INT) AS purchase_hour,
                    day_of_week, channel, store_id, payment_method,
                    CAST(returned AS BOOLEAN) AS returned,
                    CASE WHEN return_date = '' THEN NULL ELSE CAST(return_date AS TIMESTAMP) END AS return_date,
                    CASE WHEN return_reason = '' THEN NULL ELSE return_reason END AS return_reason
                FROM read_files('{VOLUME_PATH}/transactions.csv', format => 'csv', header => true)
            """,
            table_comment="Retail purchase transactions over 2 years (2023-2024). Each row is a line item in an order. Use order_id to group line items into baskets.",
            comments={
                "transaction_id": "Unique line item identifier (TXN prefix + date + sequence).",
                "order_id": "Order identifier grouping line items into a single basket/purchase. Multiple rows can share the same order_id.",
                "customer_id": "Customer identifier (CUST prefix). Links to customers table.",
                "product_id": "Product identifier matching the Neo4j product catalog. Use for cross-referencing with graph-based recommendations.",
                "total_price": "Final price after discount: quantity * unit_price * (1 - discount_pct).",
                "channel": "Purchase channel: online, in_store, or mobile_app.",
                "store_id": "Store identifier for in_store purchases. Empty string for online/mobile_app. Links to stores table.",
                "returned": "Whether the item was returned (true/false).",
                "return_reason": "Reason for return: wrong_size, defective, changed_mind, or not_as_described. NULL if not returned.",
            },
        ),
        TableDef(
            name=f"{FQN}.customers",
            select_sql=f"""
                SELECT
                    customer_id, segment,
                    CAST(signup_date AS DATE) AS signup_date,
                    preferred_channel, city, state, age_group
                FROM read_files('{VOLUME_PATH}/customers.csv', format => 'csv', header => true)
            """,
            table_comment="Customer dimension table with 5,000 customers across 4 segments: loyal, occasional, new, bargain_hunter.",
            comments={
                "segment": "Customer segment: loyal (high frequency, low discount), occasional (medium), new (low frequency, high discount), bargain_hunter (high frequency, high discount).",
                "preferred_channel": "Customer preferred purchase channel: online, in_store, or mobile_app.",
            },
        ),
        TableDef(
            name=f"{FQN}.reviews",
            select_sql=f"""
                SELECT
                    review_id, transaction_id, customer_id, product_id,
                    CAST(rating AS INT) AS rating,
                    CAST(review_date AS TIMESTAMP) AS review_date,
                    CAST(verified_purchase AS BOOLEAN) AS verified_purchase
                FROM read_files('{VOLUME_PATH}/reviews.csv', format => 'csv', header => true)
            """,
            table_comment="Product reviews linked to transactions. Ratings 1-5, weighted toward positive (mean ~4.0). All reviews are verified purchases.",
            comments={
                "rating": "Product rating from 1 (worst) to 5 (best). Distribution weighted toward positive (mean ~4.0).",
                "verified_purchase": "Always true — all reviews are linked to actual transactions.",
            },
        ),
        TableDef(
            name=f"{FQN}.inventory_snapshots",
            select_sql=f"""
                SELECT
                    CAST(snapshot_date AS DATE) AS snapshot_date,
                    product_id,
                    CAST(stock_level AS INT) AS stock_level,
                    CAST(units_sold AS INT) AS units_sold,
                    CAST(units_received AS INT) AS units_received,
                    stock_status
                FROM read_files('{VOLUME_PATH}/inventory_snapshots.csv', format => 'csv', header => true)
            """,
            table_comment="Daily inventory levels per product over 2 years. Tracks stock level, units sold, units received, and stock status.",
            comments={
                "stock_status": "Stock status: in_stock, low_stock, or out_of_stock based on current level vs reorder point.",
                "units_received": "Units received from replenishment. Non-zero when stock dipped below reorder point.",
            },
        ),
        TableDef(
            name=f"{FQN}.stores",
            select_sql=f"""
                SELECT
                    store_id, store_name, city, state, region,
                    CAST(opened_date AS DATE) AS opened_date
                FROM read_files('{VOLUME_PATH}/stores.csv', format => 'csv', header => true)
            """,
            table_comment="Store dimension table with 20 physical retail locations across US regions.",
        ),
        TableDef(
            name=f"{FQN}.knowledge_articles",
            select_sql=f"""
                SELECT
                    article_id, product_id, document_type, title, content
                FROM read_files('{VOLUME_PATH}/knowledge_articles.csv', format => 'csv', header => true)
            """,
            table_comment="Product knowledge base articles including manuals, FAQs, and troubleshooting guides. 4 articles per product.",
            comments={
                "article_id": "Unique article identifier (KA prefix + sequence).",
                "product_id": "Product identifier matching the Neo4j product catalog.",
                "document_type": "Article type: Manual, FAQ, or Troubleshooting.",
                "title": "Article title describing the topic.",
                "content": "Full article text with symptoms, solutions, and product-specific guidance.",
            },
        ),
        TableDef(
            name=f"{FQN}.support_tickets",
            select_sql=f"""
                SELECT
                    ticket_id, product_id, status, issue_description, resolution_text
                FROM read_files('{VOLUME_PATH}/support_tickets.csv', format => 'csv', header => true)
            """,
            table_comment="Customer support tickets with issue descriptions and resolutions. 4 tickets per product (3 closed, 1 open).",
            comments={
                "ticket_id": "Unique ticket identifier (T prefix + sequence).",
                "product_id": "Product identifier matching the Neo4j product catalog.",
                "status": "Ticket status: Open or Closed.",
                "issue_description": "Customer-reported issue description.",
                "resolution_text": "Support agent resolution notes. Empty string for open tickets.",
            },
        ),
        TableDef(
            name=f"{FQN}.product_reviews",
            select_sql=f"""
                SELECT
                    review_id, product_id,
                    CAST(rating AS INT) AS rating,
                    CAST(date AS DATE) AS date,
                    raw_text
                FROM read_files('{VOLUME_PATH}/product_reviews.csv', format => 'csv', header => true)
            """,
            table_comment="Curated product reviews with full text. 4 reviews per product with a mix of ratings. Distinct from the transactional reviews table which has higher volume but no text.",
            comments={
                "review_id": "Unique review identifier (R prefix + sequence).",
                "product_id": "Product identifier matching the Neo4j product catalog.",
                "rating": "Product rating from 1 (worst) to 5 (best).",
                "date": "Date the review was submitted.",
                "raw_text": "Full review text written by the customer.",
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Databricks SDK helpers
# ---------------------------------------------------------------------------


def get_client():
    """Create a Databricks WorkspaceClient using the configured profile."""
    from databricks.sdk import WorkspaceClient

    if DATABRICKS_PROFILE:
        return WorkspaceClient(profile=DATABRICKS_PROFILE)
    return WorkspaceClient()


def find_warehouse_id(client, warehouse_name: str) -> str:
    """Find a SQL warehouse by name and return its ID."""
    for wh in client.warehouses.list():
        if wh.name == warehouse_name:
            return wh.id
    raise RuntimeError(
        f"Warehouse '{warehouse_name}' not found. "
        "Set DATABRICKS_WAREHOUSE in .env to the name of an existing SQL Warehouse."
    )


def execute_sql(client, warehouse_id: str, sql: str, timeout_seconds: int = 600) -> None:
    """Execute a SQL statement on a warehouse via the Statement Execution API."""
    from databricks.sdk.service.sql import (
        Disposition,
        ExecuteStatementRequestOnWaitTimeout,
        Format,
        StatementState,
    )

    response = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
    )

    elapsed = 0
    poll_interval = 5
    while response.status and response.status.state in (
        StatementState.PENDING,
        StatementState.RUNNING,
    ):
        if elapsed >= timeout_seconds:
            if response.statement_id:
                client.statement_execution.cancel_execution(response.statement_id)
            raise TimeoutError(f"SQL execution timed out after {timeout_seconds}s")

        time.sleep(poll_interval)
        elapsed += poll_interval

        if response.statement_id:
            response = client.statement_execution.get_statement(response.statement_id)

    if response.status and response.status.state == StatementState.FAILED:
        raise RuntimeError(f"SQL execution failed: {response.status.error}")

    return response


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def upload_csvs(client) -> None:
    """Upload CSV files to a Unity Catalog Volume using the SDK Files API."""
    print(f"\nUploading CSVs to {VOLUME_PATH}/...")

    for csv_file in CSV_FILES:
        filepath = DATA_DIR / csv_file
        if not filepath.exists():
            print(f"  SKIP {csv_file} (not found)")
            continue

        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"  Uploading {csv_file} ({size_mb:.1f} MB)...", end=" ", flush=True)

        target_path = f"{VOLUME_PATH}/{csv_file}"
        with open(filepath, "rb") as f:
            client.files.upload(target_path, f, overwrite=True)

        print("OK")

    print("  Upload complete.")


def create_tables(client, warehouse_id: str, table_defs: list[TableDef]) -> None:
    """Create Delta Lake tables from the uploaded CSVs."""
    print("\nCreating Delta Lake tables...")

    for table_def in table_defs:
        print(f"  Creating {table_def.name}...", end=" ", flush=True)
        execute_sql(
            client, warehouse_id,
            f"CREATE OR REPLACE TABLE {table_def.name} USING DELTA AS {table_def.select_sql}",
        )
        print("OK")

    print("  All tables created.")


def _escape_sql_string(value: str) -> str:
    """Escape single quotes for SQL string literals."""
    return value.replace("'", "''")


def add_comments(client, warehouse_id: str, table_defs: list[TableDef]) -> None:
    """Add table and column comments for Genie compatibility."""
    print("\nAdding comments...")
    count = 0

    for table_def in table_defs:
        if table_def.table_comment:
            escaped = _escape_sql_string(table_def.table_comment)
            execute_sql(
                client, warehouse_id,
                f"COMMENT ON TABLE {table_def.name} IS '{escaped}'",
            )
            count += 1

        for col_name, col_comment in table_def.comments.items():
            escaped = _escape_sql_string(col_comment)
            execute_sql(
                client, warehouse_id,
                f"COMMENT ON COLUMN {table_def.name}.{col_name} IS '{escaped}'",
            )
            count += 1

    print(f"  Added {count} comments.")


def verify_tables(client, warehouse_id: str, table_defs: list[TableDef]) -> None:
    """Verify tables are queryable and show row counts."""
    print("\nVerifying tables...")

    for table_def in table_defs:
        resp = execute_sql(client, warehouse_id, f"SELECT COUNT(*) FROM {table_def.name}")
        row_count = "?"
        if resp and resp.result and resp.result.data_array:
            row_count = resp.result.data_array[0][0]
        print(f"  {table_def.name}: {row_count} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Databricks lakehouse tables")
    parser.add_argument("--skip-upload", action="store_true", help="Skip CSV upload")
    parser.add_argument("--skip-tables", action="store_true", help="Skip table creation")
    args = parser.parse_args()

    # Verify CSVs exist
    missing = [f for f in CSV_FILES if not (DATA_DIR / f).exists()]
    if missing and not args.skip_upload:
        print(f"ERROR: Missing CSV files in {DATA_DIR}: {missing}")
        print("Run: python -m retail_agent.scripts.generate_transactions --expanded")
        return

    if not DATABRICKS_WAREHOUSE:
        print("ERROR: DATABRICKS_WAREHOUSE env var is required (SQL warehouse name).")
        return

    client = get_client()
    warehouse_id = find_warehouse_id(client, DATABRICKS_WAREHOUSE)
    print(f"Using warehouse: {DATABRICKS_WAREHOUSE} ({warehouse_id})")

    table_defs = _build_table_defs()

    if not args.skip_upload:
        upload_csvs(client)

    if not args.skip_tables:
        create_tables(client, warehouse_id, table_defs)
        add_comments(client, warehouse_id, table_defs)
        verify_tables(client, warehouse_id, table_defs)

    print("\nDone!")


if __name__ == "__main__":
    main()
