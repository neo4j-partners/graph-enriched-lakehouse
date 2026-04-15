# Databricks notebook source
"""
Setup orchestrator for Finance Genie.

Handles all environment preparation:
  - Catalog, schema, and volume creation
  - Synthetic fraud dataset generation into Delta tables
  - Neo4j secret scope creation and credential storage
  - Neo4j connectivity verification

Fraud labels are withheld from the operational Delta tables so Genie
cannot trivially surface fraud with a column filter. The accounts and
transactions tables carry no is_fraud / is_fraud_txn columns. Labels
live exclusively in account_labels, which is used in notebook 03 for
model training and evaluation.

Called by "00_required_setup" via %run.
"""



# ── Workspace helpers ─────────────────────────────────────────────────

def get_username() -> str:
    """Return the current Databricks username."""
    return spark.sql("SELECT current_user()").first()[0]  # noqa: F821


def derive_catalog_name(prefix: str, username: str) -> str:
    """Derive a catalog name from prefix and username.

    Takes the local part of the email address and replaces dots and
    hyphens with underscores to form a valid catalog identifier.
    """
    user_part = username.split("@")[0]
    user_part = user_part.replace(".", "_").replace("-", "_")
    return f"{prefix}_{user_part}"


# ── Catalog / schema / volume setup ──────────────────────────────────

def setup_catalog_and_schema(catalog_name: str, schema_name: str, volume_name: str) -> dict:
    """Create catalog, schema, and volume if they do not exist.

    Returns a dict with catalog, schema, volume names and the full volume path.
    """
    print("=" * 70)
    print("STEP 1: Creating Catalog, Schema, and Volume")
    print("=" * 70)

    print(f"\n  Creating catalog: {catalog_name}")
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog_name}`")  # noqa: F821
        print(f"  [OK] Catalog {catalog_name!r} ready")
    except Exception as e:
        print(f"  [FAIL] Could not create catalog: {e}")
        print("  You may need CREATE CATALOG permission. Ask your workspace admin.")
        raise

    spark.sql(f"USE CATALOG `{catalog_name}`")  # noqa: F821

    print(f"\n  Creating schema: {schema_name}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{schema_name}`")  # noqa: F821
    print(f"  [OK] Schema {schema_name!r} ready")

    spark.sql(f"USE SCHEMA `{schema_name}`")  # noqa: F821

    print(f"\n  Creating volume: {volume_name}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS `{volume_name}`")  # noqa: F821
    volume_path = f"/Volumes/{catalog_name}/{schema_name}/{volume_name}"
    print(f"  [OK] Volume {volume_name!r} ready")
    print(f"\n  Volume path: {volume_path}")

    return {
        "catalog":     catalog_name,
        "schema":      schema_name,
        "volume":      volume_name,
        "volume_path": volume_path,
    }


# ── Data loading ──────────────────────────────────────────────────────

def load_data_from_volume(catalog_name: str, schema_name: str, volume_path: str) -> dict:
    """Read the five synthetic-fraud CSVs from a Unity Catalog volume and
    write them as Delta tables.

    The CSVs must already exist in volume_path. The workshop admin generates
    them locally with setup/generate_data.py and uploads them to the volume
    before participants run this notebook.

    Returns a dict of row counts keyed by table name.
    """
    from pyspark.sql.types import (  # noqa: F821
        BooleanType, DoubleType, IntegerType, StringType, StructField, StructType,
    )

    print("\n" + "=" * 70)
    print("STEP 2: Loading Synthetic Financial Dataset from Volume")
    print("=" * 70)

    def _load(filename, schema, table):
        df = (
            spark.read.format("csv")  # noqa: F821
            .option("header", "true")
            .schema(schema)
            .load(f"{volume_path}/{filename}")
        )
        (
            df.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(f"{catalog_name}.{schema_name}.{table}")
        )
        return df.count()

    n_accounts = _load("accounts.csv", StructType([
        StructField("account_id",   IntegerType()),
        StructField("account_hash", StringType()),
        StructField("account_type", StringType()),
        StructField("region",       StringType()),
        StructField("balance",      DoubleType()),
        StructField("opened_date",  StringType()),
        StructField("holder_age",   IntegerType()),
    ]), "accounts")
    print(f"\n  [OK] accounts: {n_accounts:,} rows")

    n_labels = _load("account_labels.csv", StructType([
        StructField("account_id", IntegerType()),
        StructField("is_fraud",   BooleanType()),
    ]), "account_labels")
    print(f"  [OK] account_labels: {n_labels:,} rows  (evaluation only — not in Genie space)")

    n_merchants = _load("merchants.csv", StructType([
        StructField("merchant_id",   IntegerType()),
        StructField("merchant_name", StringType()),
        StructField("category",      StringType()),
        StructField("risk_tier",     StringType()),
        StructField("region",        StringType()),
    ]), "merchants")
    print(f"  [OK] merchants: {n_merchants:,} rows")

    n_txn = _load("transactions.csv", StructType([
        StructField("txn_id",        IntegerType()),
        StructField("account_id",    IntegerType()),
        StructField("merchant_id",   IntegerType()),
        StructField("amount",        DoubleType()),
        StructField("txn_timestamp", StringType()),
        StructField("txn_hour",      IntegerType()),
    ]), "transactions")
    print(f"  [OK] transactions: {n_txn:,} rows")

    n_links = _load("account_links.csv", StructType([
        StructField("link_id",            IntegerType()),
        StructField("src_account_id",     IntegerType()),
        StructField("dst_account_id",     IntegerType()),
        StructField("amount",             DoubleType()),
        StructField("transfer_timestamp", StringType()),
    ]), "account_links")
    print(f"  [OK] account_links: {n_links:,} rows")

    return {
        "accounts":       n_accounts,
        "account_labels": n_labels,
        "merchants":      n_merchants,
        "transactions":   n_txn,
        "account_links":  n_links,
    }


# ── Neo4j secrets ─────────────────────────────────────────────────────

def setup_neo4j_secrets(
    scope_name: str,
    neo4j_url: str,
    neo4j_username: str,
    neo4j_password: str,
) -> bool:
    """Create a Databricks secret scope and store Neo4j credentials.

    Uses the Databricks SDK WorkspaceClient because dbutils.secrets
    supports reading secrets but not writing them. Stores three secrets:
    uri, username, password. All subsequent notebooks read from this scope.
    """
    from databricks.sdk import WorkspaceClient

    print("\n" + "=" * 70)
    print("STEP 3: Configuring Neo4j Secrets")
    print("=" * 70)

    w = WorkspaceClient()

    print(f"\n  Creating secret scope: {scope_name}")
    try:
        w.secrets.create_scope(scope=scope_name)
        print(f"  [OK] Scope {scope_name!r} created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  [OK] Scope {scope_name!r} already exists")
        else:
            print(f"  [FAIL] Could not create scope: {e}")
            raise

    for key, value in {"uri": neo4j_url, "username": neo4j_username, "password": neo4j_password}.items():
        print(f"  Storing secret: {key}")
        try:
            w.secrets.put_secret(scope=scope_name, key=key, string_value=value)
            print(f"  [OK] {key} stored")
        except Exception as e:
            print(f"  [FAIL] Could not store {key}: {e}")
            raise

    return True


# ── Neo4j connectivity check ──────────────────────────────────────────

def verify_neo4j_connection(neo4j_url: str, neo4j_username: str, neo4j_password: str) -> bool:
    """Verify that Neo4j is reachable using the Python driver."""
    print("\n" + "=" * 70)
    print("STEP 4: Verifying Neo4j Connection")
    print("=" * 70)

    try:
        from neo4j import GraphDatabase

        print(f"\n  Connecting to: {neo4j_url}")
        driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_username, neo4j_password))

        with driver.session(database="neo4j") as session:
            record = session.run("RETURN 'Connected' AS status").single()
            print(f"  [OK] Neo4j responded: {record['status']}")

        driver.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Could not connect to Neo4j: {e}")
        print("\n  Check that:")
        print("    - The Neo4j URI starts with neo4j+s:// for Aura")
        print("    - The username and password are correct")
        print("    - The Neo4j instance is running")
        return False


# ── Summary ───────────────────────────────────────────────────────────

def print_summary(info: dict) -> None:
    """Print a formatted summary of the setup results."""
    counts = info["table_counts"]
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print(f"""
  Catalog:     {info['catalog']}
  Schema:      {info['schema']}
  Volume:      {info['volume']}

  Delta Tables:
    accounts:        {counts['accounts']:,} rows
    account_labels:  {counts['account_labels']:,} rows  (evaluation only — not in Genie space)
    merchants:       {counts['merchants']:,} rows
    transactions:    {counts['transactions']:,} rows
    account_links:   {counts['account_links']:,} rows

  Neo4j URL:   {info['neo4j_url']}
  Scope:       {info['scope_name']}

  Neo4j connection: {'OK' if info['neo4j_connected'] else 'FAILED'}
""")
    print("=" * 70)

    if info["neo4j_connected"]:
        print("\n  You are ready to proceed to 01_neo4j_ingest.")
    else:
        print("\n  Fix the Neo4j connection before proceeding.")
