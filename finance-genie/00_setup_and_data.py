# Databricks notebook source
# MAGIC %md
# MAGIC # Graph-Augmented Intelligence — Webinar
# MAGIC ## Notebook 00: Setup & Synthetic Fraud Dataset
# MAGIC
# MAGIC Creates a realistic financial transaction graph in Delta Lake:
# MAGIC
# MAGIC | Table | Rows | Description |
# MAGIC |-------|------|-------------|
# MAGIC | `accounts` | 5 000 | Bank accounts with KYC attributes |
# MAGIC | `merchants` | 500 | Merchants with category and risk tier |
# MAGIC | `transactions` | 50 000 | Transactions linking accounts ↔ merchants |
# MAGIC | `account_links` | 8 000 | Peer-to-peer transfers between accounts |
# MAGIC
# MAGIC A small percentage of accounts are **planted as fraudulent** with realistic
# MAGIC patterns: high fan-out, shared merchants, unusual hours.

# COMMAND ----------

# MAGIC %md ## 0. Configuration

# COMMAND ----------

CATALOG = "graph_feature_engineering_demo"
SCHEMA  = "neo4j_webinar"

NEO4J_URI      = dbutils.secrets.get("neo4j-graph-engineering", "uri")        # neo4j+s://xxx.databases.neo4j.io
NEO4J_USER     = dbutils.secrets.get("neo4j-graph-engineering", "username")   # neo4j
NEO4J_PASSWORD = dbutils.secrets.get("neo4j-graph-engineering", "password")   # from Aura credentials file

# COMMAND ----------

# Try to use the catalog first. CREATE CATALOG IF NOT EXISTS still validates
# the metastore storage root URL even when the catalog already exists, so on
# workspaces without a default storage location configured it will fail with
# "Metastore storage root URL does not exist". USE CATALOG is a pure lookup
# and skips that check entirely.
try:
    spark.sql(f"USE CATALOG {CATALOG}")
except Exception:
    # Catalog does not exist — try to create it. If this raises a storage
    # root URL error, create the catalog in the Catalog Explorer UI
    # (Catalog → Create catalog → Default Storage) and re-run this cell.
    spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    spark.sql(f"USE CATALOG {CATALOG}")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
spark.sql(f"USE SCHEMA {SCHEMA}")
print(f"Using {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md ## 1. Install Dependencies

# COMMAND ----------

# MAGIC %pip install graphdatascience --quiet

# COMMAND ----------

# MAGIC %md ## 2. Generate Synthetic Accounts

# COMMAND ----------

import random, hashlib
from datetime import datetime, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import *

random.seed(42)

NUM_ACCOUNTS  = 5000
NUM_MERCHANTS = 500
NUM_TXN       = 50000
NUM_P2P       = 8000
FRAUD_RATE    = 0.04  # 4% of accounts are fraudulent

# ---- Accounts ----
account_types = ["checking", "savings", "business"]
regions       = ["US-East", "US-West", "US-Central", "EU-West", "EU-East", "APAC"]

fraud_ids = set(random.sample(range(1, NUM_ACCOUNTS + 1), int(NUM_ACCOUNTS * FRAUD_RATE)))

accounts = []
for i in range(1, NUM_ACCOUNTS + 1):
    is_fraud = i in fraud_ids
    open_date = datetime(2018, 1, 1) + timedelta(days=random.randint(0, 1800))
    accounts.append((
        i,
        hashlib.md5(f"acct-{i}".encode()).hexdigest()[:12],
        random.choice(account_types),
        random.choice(regions),
        round(random.uniform(100, 500000), 2),
        open_date.strftime("%Y-%m-%d"),
        random.randint(18, 80),
        is_fraud,
    ))

accounts_schema = StructType([
    StructField("account_id", IntegerType()),
    StructField("account_hash", StringType()),
    StructField("account_type", StringType()),
    StructField("region", StringType()),
    StructField("balance", DoubleType()),
    StructField("opened_date", StringType()),
    StructField("holder_age", IntegerType()),
    StructField("is_fraud", BooleanType()),
])

accounts_df = spark.createDataFrame(accounts, accounts_schema)
accounts_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.accounts")
print(f"accounts: {accounts_df.count()} rows  |  fraud: {accounts_df.filter('is_fraud').count()}")

# COMMAND ----------

# MAGIC %md ## 3. Generate Merchants

# COMMAND ----------

categories = ["retail", "online", "restaurant", "travel", "crypto", "gaming", "grocery", "utilities"]
risk_tiers = ["low", "medium", "high"]

merchants = []
for i in range(1, NUM_MERCHANTS + 1):
    cat = random.choice(categories)
    # crypto/gaming merchants are more likely high-risk
    if cat in ("crypto", "gaming"):
        tier = random.choices(risk_tiers, weights=[0.1, 0.3, 0.6])[0]
    else:
        tier = random.choices(risk_tiers, weights=[0.6, 0.3, 0.1])[0]
    merchants.append((
        i,
        f"merchant_{i:04d}",
        cat,
        tier,
        random.choice(regions),
    ))

merchants_schema = StructType([
    StructField("merchant_id", IntegerType()),
    StructField("merchant_name", StringType()),
    StructField("category", StringType()),
    StructField("risk_tier", StringType()),
    StructField("region", StringType()),
])

merchants_df = spark.createDataFrame(merchants, merchants_schema)
merchants_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.merchants")
print(f"merchants: {merchants_df.count()} rows")

# COMMAND ----------

# MAGIC %md ## 4. Generate Transactions (Account → Merchant)
# MAGIC
# MAGIC Fraud signals in individual transactions are **deliberately subtle** —
# MAGIC slightly higher amounts, slightly more uniform hours. The real signal
# MAGIC lives in the **graph structure** (dense P2P rings, shared merchants).

# COMMAND ----------

high_risk_merchants = [m[0] for m in merchants if m[3] == "high"]
all_merchant_ids    = list(range(1, NUM_MERCHANTS + 1))

transactions = []
for txn_id in range(1, NUM_TXN + 1):
    acct_id  = random.randint(1, NUM_ACCOUNTS)
    is_fraud = acct_id in fraud_ids

    # Fraud accounts have a slight preference for high-risk merchants
    # (subtle — not enough for tabular models to separate cleanly)
    if is_fraud and random.random() < 0.35:
        merch_id = random.choice(high_risk_merchants)
    else:
        merch_id = random.choice(all_merchant_ids)

    # Fraud amounts: drawn from the SAME lognormal distribution as legitimate,
    # but with a slightly shifted mean — overlap is intentionally high so
    # tabular features alone can't perfectly separate fraud vs legitimate.
    if is_fraud:
        amount = round(random.lognormvariate(4.4, 1.3), 2)
        hour = random.choices(range(24), weights=[2]*6 + [2]*12 + [2]*6)[0]  # slightly more uniform
    else:
        amount = round(random.lognormvariate(4.0, 1.2), 2)
        hour = random.choices(range(24), weights=[1]*6 + [4]*12 + [2]*6)[0]

    ts = datetime(2024, 1, 1) + timedelta(
        days=random.randint(0, 89),
        hours=hour,
        minutes=random.randint(0, 59),
    )

    transactions.append((
        txn_id,
        acct_id,
        merch_id,
        amount,
        ts.strftime("%Y-%m-%d %H:%M:%S"),
        hour,
        is_fraud,
    ))

txn_schema = StructType([
    StructField("txn_id", IntegerType()),
    StructField("account_id", IntegerType()),
    StructField("merchant_id", IntegerType()),
    StructField("amount", DoubleType()),
    StructField("txn_timestamp", StringType()),
    StructField("txn_hour", IntegerType()),
    StructField("is_fraud_txn", BooleanType()),
])

txn_df = spark.createDataFrame(transactions, txn_schema)
txn_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.transactions")
print(f"transactions: {txn_df.count()} rows  |  fraud txns: {txn_df.filter('is_fraud_txn').count()}")

# COMMAND ----------

# MAGIC %md ## 5. Generate Account-to-Account Links (P2P Transfers)
# MAGIC
# MAGIC Fraud rings share money between accounts.

# COMMAND ----------

fraud_list = list(fraud_ids)
normal_ids = [i for i in range(1, NUM_ACCOUNTS + 1) if i not in fraud_ids]

p2p_links = []
for link_id in range(1, NUM_P2P + 1):
    # 60% of P2P links are within the fraud ring — creates dense clusters
    # that PageRank and Louvain can detect even when tabular signals are weak
    if random.random() < 0.6 and len(fraud_list) >= 2:
        src, dst = random.sample(fraud_list, 2)
    else:
        src = random.choice(range(1, NUM_ACCOUNTS + 1))
        dst = random.choice(range(1, NUM_ACCOUNTS + 1))
        while dst == src:
            dst = random.choice(range(1, NUM_ACCOUNTS + 1))

    amount = round(random.lognormvariate(5.0, 1.5), 2)
    ts = datetime(2024, 1, 1) + timedelta(
        days=random.randint(0, 89),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    p2p_links.append((
        link_id,
        src,
        dst,
        amount,
        ts.strftime("%Y-%m-%d %H:%M:%S"),
    ))

p2p_schema = StructType([
    StructField("link_id", IntegerType()),
    StructField("src_account_id", IntegerType()),
    StructField("dst_account_id", IntegerType()),
    StructField("amount", DoubleType()),
    StructField("transfer_timestamp", StringType()),
])

p2p_df = spark.createDataFrame(p2p_links, p2p_schema)
p2p_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{CATALOG}.{SCHEMA}.account_links")
print(f"account_links: {p2p_df.count()} rows")

# COMMAND ----------

# MAGIC %md ## 6. Verify

# COMMAND ----------

for t in ["accounts", "merchants", "transactions", "account_links"]:
    cnt = spark.table(f"{CATALOG}.{SCHEMA}.{t}").count()
    print(f"  {t:20s}: {cnt:>6,} rows")

# COMMAND ----------

# MAGIC %md ## 7. Quick EDA — Fraud Distribution

# COMMAND ----------

display(
    spark.sql(f"""
        SELECT
            a.is_fraud,
            COUNT(DISTINCT a.account_id) AS num_accounts,
            COUNT(t.txn_id)              AS num_transactions,
            ROUND(AVG(t.amount), 2)      AS avg_txn_amount,
            ROUND(SUM(t.amount), 2)      AS total_volume
        FROM {CATALOG}.{SCHEMA}.accounts a
        LEFT JOIN {CATALOG}.{SCHEMA}.transactions t ON a.account_id = t.account_id
        GROUP BY a.is_fraud
    """)
)

# COMMAND ----------

# MAGIC %md
# MAGIC **Next →** `01_neo4j_ingest` — push this data into Neo4j via the Spark Connector.
