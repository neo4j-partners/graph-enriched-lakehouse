"""Pull GDS features from Neo4j and write enriched gold tables to Delta Lake.

This agent module is the source of truth for the gold tables the after-GDS
Genie Space reads. `workshop/03_pull_gold_tables.ipynb` will be synced to
match in phase 11e.

Writes three tables into `graph-enriched-lakehouse.graph-enriched-schema`:
  gold_accounts                   account metadata + GDS features + community
                                  aggregates + fraud_risk_tier (16 cols)
  gold_account_similarity_pairs   pair-level similarity + same_community flag
  gold_fraud_ring_communities     per-community summary for ring-level queries

Usage (from finance-genie/automated/ with .env in place):
    python -m cli upload --all
    python -m cli submit pull_gold_tables.py
    python -m cli logs

Cluster prerequisite: the Neo4j Spark Connector JAR must be installed as a
cluster library before submitting this job:
    org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3

Run `validation/validate_cluster.py` locally before submitting to confirm.
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

from pyspark.sql import SparkSession, Window  # noqa: E402
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
# 6. Build gold_accounts with community aggregates + fraud_risk_tier          #
#                                                                              #
#    Q1 (fillna): targeted fillna on inbound_transfer_events only; community_ #
#    id / risk_score / similarity_score stay null for unscored accounts so   #
#    window functions do not bucket them into a synthetic community_id=0.   #
#                                                                              #
#    Q3 (section ordering): gold_df is cached in memory and reused in Sec 7 #
#    and Sec 8. No write-then-read cycle.                                    #
# --------------------------------------------------------------------------- #
GOLD_ACCOUNTS_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_accounts"

inbound_counts = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.account_links")
    .groupBy(F.col("dst_account_id").alias("account_id"))
    .agg(F.count("*").alias("inbound_transfer_events"))
)

w_community = Window.partitionBy("community_id")
w_community_rank = Window.partitionBy("community_id").orderBy(F.desc("risk_score"))

gold_df = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.accounts")
    .join(graph_features_df, "account_id", "left")
    .join(inbound_counts, "account_id", "left")
    .fillna({"inbound_transfer_events": 0})
    .withColumn("community_size", F.count("*").over(w_community))
    .withColumn("community_avg_risk_score", F.avg("risk_score").over(w_community))
    .withColumn("community_risk_rank", F.rank().over(w_community_rank))
    .withColumn(
        "is_ring_community",
        (F.col("community_size").between(50, 200))
        & (F.col("community_avg_risk_score") > 1.0),
    )
    .withColumn(
        "fraud_risk_tier",
        F.when(
            F.col("is_ring_community")
            & (F.col("risk_score") > 0.5)
            & (F.col("similarity_score") > 0.05),
            "high",
        )
        .when(F.col("is_ring_community"), "medium")
        .otherwise("low"),
    )
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
        "community_size",
        "community_avg_risk_score",
        "community_risk_rank",
        "inbound_transfer_events",
        "is_ring_community",
        "fraud_risk_tier",
    )
    .cache()
)

(
    gold_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_ACCOUNTS_TABLE)
)
n_gold = spark.table(GOLD_ACCOUNTS_TABLE).count()
print(f"Written {GOLD_ACCOUNTS_TABLE} ({n_gold:,} rows, 16 columns)")

# --------------------------------------------------------------------------- #
# 7. Build gold_account_similarity_pairs with same_community flag             #
#                                                                              #
#    Q4 (null check): require both community IDs non-null before equality    #
#    so pairs where either account was unscored come out as false, not null. #
# --------------------------------------------------------------------------- #
GOLD_PAIRS_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_account_similarity_pairs"

community_lookup = gold_df.select("account_id", "community_id")

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

similarity_pairs_df = (
    similarity_pairs_df
    .join(
        community_lookup.withColumnRenamed("account_id", "account_id_a")
                        .withColumnRenamed("community_id", "community_id_a"),
        "account_id_a",
        "left",
    )
    .join(
        community_lookup.withColumnRenamed("account_id", "account_id_b")
                        .withColumnRenamed("community_id", "community_id_b"),
        "account_id_b",
        "left",
    )
    .withColumn(
        "same_community",
        F.col("community_id_a").isNotNull()
        & F.col("community_id_b").isNotNull()
        & (F.col("community_id_a") == F.col("community_id_b")),
    )
    .drop("community_id_a", "community_id_b")
)

(
    similarity_pairs_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_PAIRS_TABLE)
)
n_pairs = spark.table(GOLD_PAIRS_TABLE).count()
print(f"Written {GOLD_PAIRS_TABLE} ({n_pairs:,} rows)")

# --------------------------------------------------------------------------- #
# 8. Build gold_fraud_ring_communities — one row per Louvain community         #
#                                                                              #
#    Q2 (rank): ROW_NUMBER() instead of RANK() so tied max_risk_score values #
#    do not produce duplicate top_account_id rows.                            #
# --------------------------------------------------------------------------- #
GOLD_RING_COMMUNITIES_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_fraud_ring_communities"

ring_aggregates = (
    gold_df
    .filter(F.col("community_id").isNotNull())
    .groupBy("community_id")
    .agg(
        F.count("*").alias("member_count"),
        F.round(F.avg("risk_score"), 6).alias("avg_risk_score"),
        F.round(F.max("risk_score"), 6).alias("max_risk_score"),
        F.round(F.avg("similarity_score"), 5).alias("avg_similarity_score"),
        F.sum(F.when(F.col("risk_score") > 1.0, 1).otherwise(0))
            .alias("high_risk_member_count"),
    )
    .withColumn(
        "is_ring_candidate",
        F.col("member_count").between(50, 200) & (F.col("avg_risk_score") > 1.0),
    )
)

w_top = Window.partitionBy("community_id").orderBy(
    F.desc("risk_score"), F.asc("account_id")
)

top_accounts = (
    gold_df
    .filter(F.col("community_id").isNotNull())
    .select("community_id", "account_id", "risk_score")
    .withColumn("_row", F.row_number().over(w_top))
    .filter(F.col("_row") == 1)
    .select(
        F.col("community_id"),
        F.col("account_id").alias("top_account_id"),
    )
)

ring_communities_df = ring_aggregates.join(top_accounts, "community_id", "left")

(
    ring_communities_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_RING_COMMUNITIES_TABLE)
)
n_ring = spark.table(GOLD_RING_COMMUNITIES_TABLE).count()
n_ring_candidates = (
    spark.table(GOLD_RING_COMMUNITIES_TABLE)
    .filter(F.col("is_ring_candidate"))
    .count()
)
print(
    f"Written {GOLD_RING_COMMUNITIES_TABLE} "
    f"({n_ring:,} rows, {n_ring_candidates} ring candidates)"
)

# --------------------------------------------------------------------------- #
# 9. Cleanup cached DataFrames                                                 #
# --------------------------------------------------------------------------- #
gold_df.unpersist()
graph_features_df.unpersist()

print("Done.")
