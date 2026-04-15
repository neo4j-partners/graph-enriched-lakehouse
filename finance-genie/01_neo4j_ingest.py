# Databricks notebook source
# MAGIC %md
# MAGIC # Graph-Augmented Intelligence — Webinar
# MAGIC ## Notebook 01: Databricks → Neo4j Ingest
# MAGIC
# MAGIC Push our Delta Lake tables into Neo4j as a property graph using the
# MAGIC **Neo4j Spark Connector**. Five lines of config — that's it.
# MAGIC
# MAGIC ```
# MAGIC ┌──────────────┐    Spark Connector    ┌──────────────┐
# MAGIC │  Delta Lake   │ ──────────────────► │    Neo4j      │
# MAGIC │  (accounts,   │                      │  (:Account)   │
# MAGIC │   merchants,  │                      │  (:Merchant)  │
# MAGIC │   txns, p2p)  │                      │  [:TRANSACTED]│
# MAGIC └──────────────┘                      │  [:TRANSFERRED]│
# MAGIC                                        └──────────────┘
# MAGIC ```

# COMMAND ----------

# MAGIC %md ## 0. Configuration

# COMMAND ----------

CATALOG = "graph_feature_engineering_demo"
SCHEMA  = "neo4j_webinar"

NEO4J_URI      = dbutils.secrets.get("neo4j-graph-engineering", "uri")
NEO4J_USER     = dbutils.secrets.get("neo4j-graph-engineering", "username")
NEO4J_PASSWORD = dbutils.secrets.get("neo4j-graph-engineering", "password")

# Common Spark Connector options
NEO4J_OPTS = {
    "url":                    NEO4J_URI,
    "authentication.basic.username": NEO4J_USER,
    "authentication.basic.password": NEO4J_PASSWORD,
}

spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

# COMMAND ----------

# MAGIC %md ## 1. Install Dependencies

# COMMAND ----------

# MAGIC %pip install graphdatascience --quiet

# COMMAND ----------

# MAGIC %md ## 2. Clear Neo4j (idempotent re-runs)
# MAGIC
# MAGIC Optional: wipe previous graph so the demo is repeatable.

# COMMAND ----------

from graphdatascience import GraphDataScience

gds = GraphDataScience(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
gds.run_cypher("MATCH (n) DETACH DELETE n")
print("Neo4j cleared.")

# COMMAND ----------

# MAGIC %md ## 2. Write Account Nodes

# COMMAND ----------

accounts_df = spark.table(f"{CATALOG}.{SCHEMA}.accounts")

(accounts_df
 .write
 .format("org.neo4j.spark.DataSource")
 .mode("Overwrite")
 .options(**NEO4J_OPTS)
 .option("labels", ":Account")
 .option("node.keys", "account_id")
 .save()
)

print(f"Wrote {accounts_df.count()} Account nodes")

# COMMAND ----------

# MAGIC %md ## 3. Write Merchant Nodes

# COMMAND ----------

merchants_df = spark.table(f"{CATALOG}.{SCHEMA}.merchants")

(merchants_df
 .write
 .format("org.neo4j.spark.DataSource")
 .mode("Overwrite")
 .options(**NEO4J_OPTS)
 .option("labels", ":Merchant")
 .option("node.keys", "merchant_id")
 .save()
)

print(f"Wrote {merchants_df.count()} Merchant nodes")

# COMMAND ----------

# MAGIC %md ## 4. Write TRANSACTED_WITH Relationships (Account → Merchant)

# COMMAND ----------

txn_df = spark.table(f"{CATALOG}.{SCHEMA}.transactions")

(txn_df
 .write
 .format("org.neo4j.spark.DataSource")
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

print(f"Wrote {txn_df.count()} TRANSACTED_WITH relationships")

# COMMAND ----------

# MAGIC %md ## 5. Write TRANSFERRED_TO Relationships (Account → Account)

# COMMAND ----------

p2p_df = spark.table(f"{CATALOG}.{SCHEMA}.account_links")

(p2p_df
 .write
 .format("org.neo4j.spark.DataSource")
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

print(f"Wrote {p2p_df.count()} TRANSFERRED_TO relationships")

# COMMAND ----------

# MAGIC %md ## 6. Verify Graph in Neo4j

# COMMAND ----------

result = gds.run_cypher("""
    CALL apoc.meta.stats() YIELD nodeCount, relCount, labels, relTypes
    RETURN nodeCount, relCount, labels, relTypes
""")
display(result)

# COMMAND ----------

# MAGIC %md ### Quick Counts

# COMMAND ----------

counts = gds.run_cypher("""
    MATCH (a:Account) WITH count(a) AS accounts
    MATCH (m:Merchant) WITH accounts, count(m) AS merchants
    MATCH ()-[t:TRANSACTED_WITH]->() WITH accounts, merchants, count(t) AS txns
    MATCH ()-[p:TRANSFERRED_TO]->() WITH accounts, merchants, txns, count(p) AS p2p
    RETURN accounts, merchants, txns, p2p
""")
print(counts.to_string(index=False))

# COMMAND ----------

# MAGIC %md ### Sample: One Account's Neighbourhood

# COMMAND ----------

sample = gds.run_cypher("""
    MATCH (a:Account {is_fraud: true})-[r]->(target)
    WITH a, type(r) AS rel_type, labels(target)[0] AS target_type, count(*) AS cnt
    RETURN a.account_id AS account, rel_type, target_type, cnt
    ORDER BY cnt DESC
    LIMIT 10
""")
display(spark.createDataFrame(sample))

# COMMAND ----------

# MAGIC %md
# MAGIC **What we just did:** 4 write operations pushed our entire Delta Lake dataset into Neo4j
# MAGIC as a typed property graph — no ETL pipeline, no CSV exports, no Cypher `LOAD CSV`.
# MAGIC
# MAGIC **Next →** `02_gds_features` — run graph algorithms to extract fraud-signal features.
