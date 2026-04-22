# Workshop Guide

This workshop produces a Databricks Lakehouse catalog that answers structural
analyst questions — portfolio composition over fraud-ring communities, cohort
comparisons across risk tiers, investigator workload estimates — that the base
tables cannot reach. The enrichment pipeline runs Neo4j GDS as a silver-to-gold
stage: three graph algorithms write community membership, risk centrality, and
structural similarity back as scalar columns. Genie reads those columns the same
way it reads any other warehouse column.

**Same Databricks spend. Strictly more answers.**

**Audience:** Workshop participants running the demo interactively on Databricks.

**Prerequisite state:** The demo owner has already run the `automated/` setup
steps: data generated, tables loaded into Unity Catalog, and credentials stored
in the `neo4j-graph-engineering` secret scope.

---

## Prerequisites

Three things must be in place before the first notebook:

1. **Neo4j Spark Connector** installed as a cluster library on the dedicated
   cluster:
   ```
   org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
   ```

2. **Secret scope populated:** the `neo4j-graph-engineering` scope must contain
   `uri`, `username`, `password`, `genie_space_id_before`, and
   `genie_space_id_after`. The demo owner populates these by running
   `automated/setup_secrets.sh`. Participants can also store them interactively
   by running `00_required_setup.ipynb`.

3. **Tables loaded:** `accounts`, `merchants`, `transactions`, `account_links`,
   and `account_labels` must exist in
   `graph-enriched-lakehouse.graph-enriched-schema`. The demo owner loads them
   with `automated/upload_and_create_tables.sh`.

---

## Notebook Sequence

### 00_required_setup.ipynb

Stores Neo4j credentials and both Genie Space IDs in the
`neo4j-graph-engineering` Databricks secret scope, then verifies the Aura
connection. Run this on the dedicated cluster if the admin has not already
populated the scope.

### 01_genie_before.ipynb _(serverless)_

Runs against the BEFORE Genie Space — the space pointed at the base Silver
tables. A tabular warm-up confirms Genie is working; an analytics challenge
shows it handling joins and conditional aggregates correctly. Then five anchor
questions show where volume and frequency proxies fall short of structural
answers: merchant favorites by volume, book share for the top-decile, review
queue sized by volume cutoff, transfer ratio between repeat-transfer pairs, and
merchant concentration by co-transaction activity. These are the best answers
the base catalog can produce. After the pipeline runs, the same five questions
asked in Genie against the enriched Gold tables return structurally different
results.

### 02_neo4j_ingest.ipynb _(dedicated cluster)_

Reads the five Delta tables and writes them to Neo4j as a property graph:
`:Account` and `:Merchant` nodes, `TRANSACTED_WITH` (Account → Merchant) and
`TRANSFERRED_TO` (Account → Account) relationships. Requires the dedicated
cluster with the Neo4j Spark Connector.

### 03_gds_enrichment.ipynb _(dedicated cluster)_

Runs three GDS algorithms against the projected graph via the `graphdatascience`
Python client:

- **PageRank** — writes `risk_score` to each Account node; ring members score
  high because they receive transfers from other high-scoring ring members
- **Louvain** — writes `community_id`; each fraud ring becomes a single
  community
- **Node Similarity** — writes `similarity_score`; Jaccard normalization removes
  volume inflation and surfaces ring pairs

After this notebook completes, return to the sequence and open
`04_pull_gold_tables`.

### 04_pull_gold_tables.ipynb _(dedicated cluster)_

Reads the enriched Account nodes and similarity relationships back from Neo4j
and writes three Gold tables to Unity Catalog:

- `gold_accounts` — account metadata plus `risk_score`, `community_id`,
  `similarity_score`, and `fraud_risk_tier`
- `gold_account_similarity_pairs` — pairwise similarity scores
- `gold_fraud_ring_communities` — ring-level community aggregates with
  `is_ring_community` flag

### Genie AFTER _(live in Genie — no notebook)_

After the pipeline completes, open Genie against the enriched Gold tables and
ask the same five anchor questions from `01_genie_before`. The copy-paste
versions of the after questions are in `genie-guide.md` under **AFTER: Anchor**.
Start with merchant favorites — it closes the before/after pair most visibly.
Additional questions for extended demos and Q&A are in the **Fill-In / Q&A**
section of `genie-guide.md`.

### 06_train_model.ipynb _(optional)_

Trains a baseline gradient-boosting classifier on tabular features and a
graph-augmented classifier on all features, including `risk_score`,
`community_id`, and `similarity_score`. Both runs log to MLflow with AUC,
precision, recall, F1, and ROC curves. The final cell translates the lift in
fraud caught into an estimated dollar impact.

---

## Reference Material

- `GENIE_SETUP.md` — Genie Space instructions and column definitions for
  `fraud_risk_tier`, `risk_score`, `community_id`, and `similarity_score`
- `aura_gds_guide.md` — step-by-step GDS algorithm guide for running in the
  Neo4j Aura Query tab, an alternative to the Python-client notebook
- `diagrams/` — architecture diagrams for the workshop
