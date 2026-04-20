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

Asks four questions to the BEFORE Genie Space — the space pointed at the base
tables. A tabular warm-up confirms Genie is working. The next three questions
target hub positions, community membership, and shared-merchant similarity:
structure that lives in the transfer network topology, not in any row or column
the base tables carry. Each miss is labeled `STRUCTURAL GAP CONFIRMED` against
the ground-truth fraud rings — evidence of what the catalog cannot reach, not a
Genie limitation. A teaser question previews the portfolio query the enriched
catalog will answer in `05_genie_after`.

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

### 05_genie_after.ipynb _(serverless)_

Asks five analyst questions to the AFTER Genie Space — the space pointed at the
enriched gold tables. One question per category:

1. **Portfolio composition** — what share of accounts sits in ring-candidate
   communities, broken out by region (the teaser question from `01_genie_before`,
   now answerable)
2. **Cohort comparisons** — spending mix differences between ring-community and
   baseline accounts
3. **Community rollups** — total balance and book share held by ring-candidate
   communities
4. **Operational workload** — investigator review queue size and regional
   breakdown at the high-risk-tier bar
5. **Merchant-side** — which merchants are most commonly visited by ring-candidate
   accounts

No structural questions are re-run. Genie answers each category question using
`community_id`, `fraud_risk_tier`, and `similarity_score` as scalar columns —
the same way it answers questions against any other warehouse table.

### 06_train_model.ipynb _(optional)_

Trains a baseline gradient-boosting classifier on tabular features and a
graph-augmented classifier on all features, including `risk_score`,
`community_id`, and `similarity_score`. Both runs log to MLflow with AUC,
precision, recall, F1, and ROC curves. The final cell translates the lift in
fraud caught into an estimated dollar impact.

---

## Reference Material

- `INSTRUCTOR_NOTES.md` — objection-rebuttal guide for presenters; covers the
  "isn't Genie just doing `WHERE fraud_risk_tier = 'high'`?" question and other
  common audience challenges
- `GENIE_SETUP.md` — Genie Space instructions and column definitions for
  `fraud_risk_tier`, `risk_score`, `community_id`, and `similarity_score`
- `aura_gds_guide.md` — step-by-step GDS algorithm guide for running in the
  Neo4j Aura Query tab (alternative to the Python-client notebook)
- `GOLD_TABLE_ENRICHMENT.md` — description of the three gold tables and their
  columns
- `diagrams/` — architecture diagrams for the workshop
