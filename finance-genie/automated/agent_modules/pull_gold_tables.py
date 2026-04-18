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
from pathlib import Path

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

# __file__ is not set when the cluster runs this via exec(compile(...));
# fall back to the frame's co_filename to find our sibling modules.
try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    import inspect as _inspect
    _HERE = Path(_inspect.currentframe().f_code.co_filename).resolve().parent
    del _inspect
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pyspark.sql import SparkSession, Window  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from neo4j_secrets import load_neo4j_opts  # noqa: E402

# --------------------------------------------------------------------------- #
# 2. Config + Neo4j credentials                                                #
# --------------------------------------------------------------------------- #
CATALOG = os.environ["CATALOG"]
SCHEMA = os.environ["SCHEMA"]
SECRET_SCOPE = os.environ["NEO4J_SECRET_SCOPE"]

TIER_HIGH = "high"
TIER_MEDIUM = "medium"
TIER_LOW = "low"

RING_SIZE_LOW = 50
RING_SIZE_HIGH = 200
COMMUNITY_AVG_RISK_MIN = 1.0
HIGH_TIER_RISK_MIN = 0.5
HIGH_TIER_SIM_MIN = 0.05

NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_OPTS = load_neo4j_opts(SECRET_SCOPE)

# --------------------------------------------------------------------------- #
# 3. Spark session                                                             #
# --------------------------------------------------------------------------- #
spark = SparkSession.builder.getOrCreate()

# --------------------------------------------------------------------------- #
# 4. Read GDS features from Neo4j Account nodes                               #
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
# 5. Build gold_accounts with community aggregates + fraud_risk_tier          #
#                                                                              #
# Targeted fillna on inbound_transfer_events only — leaving community_id,     #
# risk_score, and similarity_score null for unscored accounts is intentional:  #
# a blanket fillna(0) would bucket every unscored account into a synthetic    #
# community_id=0 and poison the window aggregates.                            #
#                                                                              #
# gold_df is cached and reused in Sections 7 and 8; no write-then-read cycle. #
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
        (F.col("community_size").between(RING_SIZE_LOW, RING_SIZE_HIGH))
        & (F.col("community_avg_risk_score") > COMMUNITY_AVG_RISK_MIN),
    )
    .withColumn(
        "fraud_risk_tier",
        F.when(
            F.col("is_ring_community")
            & (F.col("risk_score") > HIGH_TIER_RISK_MIN)
            & (F.col("similarity_score") > HIGH_TIER_SIM_MIN),
            TIER_HIGH,
        )
        .when(F.col("is_ring_community"), TIER_MEDIUM)
        .otherwise(TIER_LOW),
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

n_gold = gold_df.count()  # materializes the cache; subsequent reads are free.

(
    gold_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_ACCOUNTS_TABLE)
)
print(f"Written {GOLD_ACCOUNTS_TABLE} ({n_gold:,} rows, 16 columns)")

# --------------------------------------------------------------------------- #
# 6. Build gold_account_similarity_pairs with same_community flag             #
#                                                                              #
# Both sides are guarded non-null before equality so pairs involving an        #
# unscored account come out as false, not null.                                #
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

similarity_pairs_df = similarity_pairs_df.cache()
n_pairs = similarity_pairs_df.count()

(
    similarity_pairs_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_PAIRS_TABLE)
)
print(f"Written {GOLD_PAIRS_TABLE} ({n_pairs:,} rows)")
similarity_pairs_df.unpersist()

# --------------------------------------------------------------------------- #
# 7. Build gold_fraud_ring_communities — one row per Louvain community         #
#                                                                              #
# ROW_NUMBER (not RANK) with a deterministic tiebreak on account_id so ties   #
# on max_risk_score cannot produce duplicate top_account_id rows.             #
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
        F.col("member_count").between(RING_SIZE_LOW, RING_SIZE_HIGH)
        & (F.col("avg_risk_score") > COMMUNITY_AVG_RISK_MIN),
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

ring_communities_df = ring_aggregates.join(top_accounts, "community_id", "left").cache()

ring_counts = ring_communities_df.agg(
    F.count("*").alias("total"),
    F.sum(F.col("is_ring_candidate").cast("int")).alias("candidates"),
).collect()[0]
n_ring = int(ring_counts["total"])
n_ring_candidates = int(ring_counts["candidates"] or 0)

(
    ring_communities_df
    .write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_RING_COMMUNITIES_TABLE)
)
print(
    f"Written {GOLD_RING_COMMUNITIES_TABLE} "
    f"({n_ring:,} rows, {n_ring_candidates} ring candidates)"
)

ring_communities_df.unpersist()
gold_df.unpersist()
graph_features_df.unpersist()

print("Done.")
