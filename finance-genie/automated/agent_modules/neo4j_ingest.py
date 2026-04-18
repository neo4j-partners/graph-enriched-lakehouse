"""Push Delta Lake tables into Neo4j as a property graph.

Translated from finance-genie/workshop/01_neo4j_ingest.ipynb.
Runs as a Databricks Python task (no notebook kernel required).

Usage (from finance-genie/automated/ with .env in place):
    python -m cli upload --all
    python -m cli submit neo4j_ingest.py
    python -m cli logs

Cluster prerequisites (install as cluster libraries before submitting):
    - org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3  (JAR)
    - graphdatascience  (PyPI)
"""

from __future__ import annotations

import os
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

from graphdatascience import GraphDataScience  # noqa: E402
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

(
    accounts_df.write.format("org.neo4j.spark.DataSource")
    .mode("Append")
    .options(**NEO4J_OPTS)
    .option("labels", ":Account")
    .option("node.keys", "account_id")
    .save()
)
print("Account nodes written.")

# --------------------------------------------------------------------------- #
# 8. Write Merchant nodes                                                       #
# --------------------------------------------------------------------------- #
merchants_df = spark.table(f"`{CATALOG}`.`{SCHEMA}`.merchants")

(
    merchants_df.write.format("org.neo4j.spark.DataSource")
    .mode("Append")
    .options(**NEO4J_OPTS)
    .option("labels", ":Merchant")
    .option("node.keys", "merchant_id")
    .save()
)
print("Merchant nodes written.")

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
print("TRANSACTED_WITH relationships written.")

# --------------------------------------------------------------------------- #
# 11. Write TRANSFERRED_TO relationships (Account -> Account)                   #
# --------------------------------------------------------------------------- #
p2p_df = spark.table(f"`{CATALOG}`.`{SCHEMA}`.account_links")

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
print("TRANSFERRED_TO relationships written.")

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
