"""Push Delta Lake tables into Neo4j as a property graph.

Translated from finance-genie/feature_engineering/01_neo4j_ingest.ipynb.
Runs as a Databricks Python task (no notebook kernel required).

Usage (from finance-genie/accelerator/ with .env in place):
    python -m cli upload --all
    python -m cli submit neo4j_ingest.py
    python -m cli logs

Cluster prerequisite: the Neo4j Spark Connector JAR must be installed as a
cluster library before submitting this job.
"""

from __future__ import annotations

import os
import subprocess
import sys


# --------------------------------------------------------------------------- #
# 1. Load .env extras forwarded by the runner as KEY=VALUE argv               #
#    (inlined from databricks_job_runner.inject — that package is local-only) #
# --------------------------------------------------------------------------- #
remaining: list[str] = []
for _arg in sys.argv[1:]:
    if "=" in _arg and not _arg.startswith("-"):
        _key, _, _val = _arg.partition("=")
        os.environ.setdefault(_key, _val)
    else:
        remaining.append(_arg)
sys.argv[1:] = remaining

# --------------------------------------------------------------------------- #
# 2. Install graphdatascience (replaces the notebook %pip install cell)        #
# --------------------------------------------------------------------------- #
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "graphdatascience", "--quiet"]
)

from graphdatascience import GraphDataScience  # noqa: E402 — must follow pip install
from pyspark.sql import SparkSession  # noqa: E402

# --------------------------------------------------------------------------- #
# 3. Config — pulled from os.environ after inject_params()                     #
# --------------------------------------------------------------------------- #
CATALOG = os.environ["CATALOG"]
SCHEMA = os.environ["SCHEMA"]
SECRET_SCOPE = os.environ["NEO4J_SECRET_SCOPE"]

# --------------------------------------------------------------------------- #
# 4. Fetch Neo4j credentials from Databricks Secrets (replaces dbutils)        #
# --------------------------------------------------------------------------- #
from databricks.sdk import WorkspaceClient  # noqa: E402

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
# 5. Spark session + catalog                                                   #
# --------------------------------------------------------------------------- #
spark = SparkSession.builder.getOrCreate()
spark.sql(f"USE CATALOG `{CATALOG}`")
spark.sql(f"USE SCHEMA `{SCHEMA}`")

# --------------------------------------------------------------------------- #
# 6. Clear Neo4j (idempotent re-runs)                                          #
# --------------------------------------------------------------------------- #
gds = GraphDataScience(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
gds.run_cypher("MATCH (n) DETACH DELETE n")
print("Neo4j cleared.")

# --------------------------------------------------------------------------- #
# 7. Write Account nodes                                                        #
# --------------------------------------------------------------------------- #
accounts_df = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.accounts")
    .join(spark.table(f"`{CATALOG}`.`{SCHEMA}`.account_labels"), "account_id", "left")
)
n_accounts = accounts_df.count()

(
    accounts_df.write.format("org.neo4j.spark.DataSource")
    .mode("Append")
    .options(**NEO4J_OPTS)
    .option("labels", ":Account")
    .option("node.keys", "account_id")
    .save()
)
print(f"Wrote {n_accounts} Account nodes")

# --------------------------------------------------------------------------- #
# 8. Write Merchant nodes                                                       #
# --------------------------------------------------------------------------- #
merchants_df = spark.table(f"`{CATALOG}`.`{SCHEMA}`.merchants")
n_merchants = merchants_df.count()

(
    merchants_df.write.format("org.neo4j.spark.DataSource")
    .mode("Append")
    .options(**NEO4J_OPTS)
    .option("labels", ":Merchant")
    .option("node.keys", "merchant_id")
    .save()
)
print(f"Wrote {n_merchants} Merchant nodes")

# --------------------------------------------------------------------------- #
# 9. Create indexes before relationship writes                                  #
#    Uniqueness constraints also create an index; without these the Spark      #
#    Connector does a full node scan per relationship row.                     #
# --------------------------------------------------------------------------- #
gds.run_cypher("""
    CREATE CONSTRAINT account_id_unique IF NOT EXISTS
    FOR (a:Account) REQUIRE a.account_id IS UNIQUE
""")
gds.run_cypher("""
    CREATE CONSTRAINT merchant_id_unique IF NOT EXISTS
    FOR (m:Merchant) REQUIRE m.merchant_id IS UNIQUE
""")
print("Indexes ready.")

# --------------------------------------------------------------------------- #
# 10. Write TRANSACTED_WITH relationships (Account -> Merchant)                  #
# --------------------------------------------------------------------------- #
txn_df = spark.table(f"`{CATALOG}`.`{SCHEMA}`.transactions")
n_txns = txn_df.count()

(
    txn_df.write.format("org.neo4j.spark.DataSource")
    .mode("Overwrite")
    .options(**NEO4J_OPTS)
    .option("relationship", "TRANSACTED_WITH")
    .option("relationship.save.strategy", "keys")
    .option("relationship.source.labels", ":Account")
    .option("relationship.source.node.keys", "account_id:account_id")
    .option("relationship.target.labels", ":Merchant")
    .option("relationship.target.node.keys", "merchant_id:merchant_id")
    .save()
)
print(f"Wrote {n_txns} TRANSACTED_WITH relationships")

# --------------------------------------------------------------------------- #
# 11. Write TRANSFERRED_TO relationships (Account -> Account)                   #
# --------------------------------------------------------------------------- #
p2p_df = spark.table(f"`{CATALOG}`.`{SCHEMA}`.account_links")
n_p2p = p2p_df.count()

(
    p2p_df.write.format("org.neo4j.spark.DataSource")
    .mode("Overwrite")
    .options(**NEO4J_OPTS)
    .option("relationship", "TRANSFERRED_TO")
    .option("relationship.save.strategy", "keys")
    .option("relationship.source.labels", ":Account")
    .option("relationship.source.node.keys", "src_account_id:account_id")
    .option("relationship.target.labels", ":Account")
    .option("relationship.target.node.keys", "dst_account_id:account_id")
    .save()
)
print(f"Wrote {n_p2p} TRANSFERRED_TO relationships")

# --------------------------------------------------------------------------- #
# 12. Verify — quick counts                                                     #
# --------------------------------------------------------------------------- #
counts = gds.run_cypher("""
    MATCH (a:Account) WITH count(a) AS accounts
    MATCH (m:Merchant) WITH accounts, count(m) AS merchants
    MATCH ()-[t:TRANSACTED_WITH]->() WITH accounts, merchants, count(t) AS txns
    MATCH ()-[p:TRANSFERRED_TO]->() WITH accounts, merchants, txns, count(p) AS p2p
    RETURN accounts, merchants, txns, p2p
""")
print(counts.to_string(index=False))
print("Done.")
