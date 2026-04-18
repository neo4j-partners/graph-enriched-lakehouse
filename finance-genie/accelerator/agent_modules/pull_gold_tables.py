"""Pull GDS features from Neo4j and write demo gold tables to Delta Lake.

Translated from finance-genie/feature_engineering/03_pull_gold_tables.ipynb
(sections 6–7: Build Demo Gold Table). Runs as a Databricks Python task on a
cluster with the Neo4j Spark Connector JAR installed.

Writes two tables:
  gold_accounts                   — account metadata + GDS features (no is_fraud)
  gold_account_similarity_pairs   — (account_id_a, account_id_b, similarity_score)

Usage (from finance-genie/accelerator/ with .env in place):
    python -m cli upload --all
    python -m cli submit pull_gold_tables.py
    python -m cli logs

Cluster prerequisite: the Neo4j Spark Connector JAR must be installed as a
cluster library before submitting this job:
    org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
"""

from __future__ import annotations

import os
import sys

# --------------------------------------------------------------------------- #
# 1. Load .env extras forwarded by the runner as KEY=VALUE argv               #
#    (inlined from databricks_job_runner.inject — not installed on cluster)   #
# --------------------------------------------------------------------------- #
remaining: list[str] = []
for _arg in sys.argv[1:]:
    if "=" in _arg and not _arg.startswith("-"):
        _key, _, _val = _arg.partition("=")
        os.environ.setdefault(_key, _val)
    else:
        remaining.append(_arg)
sys.argv[1:] = remaining

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

# --------------------------------------------------------------------------- #
# 2. Config                                                                   #
# --------------------------------------------------------------------------- #
CATALOG = os.environ["CATALOG"]
SCHEMA = os.environ["SCHEMA"]
SECRET_SCOPE = os.environ["NEO4J_SECRET_SCOPE"]

# --------------------------------------------------------------------------- #
# 3. Fetch Neo4j credentials from Databricks Secrets                          #
# --------------------------------------------------------------------------- #
_ws = WorkspaceClient()

NEO4J_URI = _ws.dbutils.secrets.get(scope=SECRET_SCOPE, key="uri")
NEO4J_USER = _ws.dbutils.secrets.get(scope=SECRET_SCOPE, key="username")
NEO4J_PASSWORD = _ws.dbutils.secrets.get(scope=SECRET_SCOPE, key="password")

NEO4J_OPTS = {
    "url": NEO4J_URI,
    "authentication.basic.username": NEO4J_USER,
    "authentication.basic.password": NEO4J_PASSWORD,
    "batch.size": "10000",
}

# --------------------------------------------------------------------------- #
# 4. Spark session                                                             #
# --------------------------------------------------------------------------- #
spark = SparkSession.builder.getOrCreate()

# --------------------------------------------------------------------------- #
# 5. Read GDS features from Neo4j Account nodes                               #
#    Cache so the DataFrame is only read from Neo4j once — it is reused in   #
#    the gold_accounts join and would otherwise trigger a second full read.   #
# --------------------------------------------------------------------------- #
graph_features_df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .options(**NEO4J_OPTS)
    .option("labels", "Account")
    .load()
    .select(
        F.col("account_id").cast("long"),
        F.col("risk_score").cast("double"),
        F.col("community_id").cast("long"),
        F.col("similarity_score").cast("double"),
    )
    .cache()
)
print(f"Read {graph_features_df.count():,} Account nodes with GDS features")

# --------------------------------------------------------------------------- #
# 6. Write gold_accounts                                                       #
# --------------------------------------------------------------------------- #
GOLD_ACCOUNTS_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_accounts"

gold_df = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.accounts")
    .join(graph_features_df, "account_id", "left")
    .select(
        "account_id",
        "account_hash",
        "account_type",
        "region",
        "balance",
        "opened_date",
        "holder_age",
        "risk_score",
        "community_id",
        "similarity_score",
    )
    .fillna(0)
)

(
    gold_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_ACCOUNTS_TABLE)
)
n_gold = spark.table(GOLD_ACCOUNTS_TABLE).count()
print(f"Written {GOLD_ACCOUNTS_TABLE} ({n_gold:,} rows)")

graph_features_df.unpersist()

# --------------------------------------------------------------------------- #
# 7. Write gold_account_similarity_pairs                                       #
# --------------------------------------------------------------------------- #
GOLD_PAIRS_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_account_similarity_pairs"

similarity_pairs_df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .options(**NEO4J_OPTS)
    .option("relationship", "SIMILAR_TO")
    .option("relationship.source.labels", ":Account")
    .option("relationship.target.labels", ":Account")
    .load()
    .select(
        F.least(
            F.col("`source.account_id`"), F.col("`target.account_id`")
        ).cast("long").alias("account_id_a"),
        F.greatest(
            F.col("`source.account_id`"), F.col("`target.account_id`")
        ).cast("long").alias("account_id_b"),
        F.col("`rel.similarity_score`").cast("double").alias("similarity_score"),
    )
    .dropDuplicates(["account_id_a", "account_id_b"])
)

(
    similarity_pairs_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_PAIRS_TABLE)
)
n_pairs = spark.table(GOLD_PAIRS_TABLE).count()
print(f"Written {GOLD_PAIRS_TABLE} ({n_pairs:,} rows)")
print("Done.")
