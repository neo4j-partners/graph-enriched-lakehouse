# Workshop Guide

**Audience:** Workshop participants running the demo interactively on Databricks.

**Prerequisite state:** The demo owner has already run the `automated/` setup steps — data generated, tables loaded into Unity Catalog, and Neo4j credentials stored in the `neo4j-graph-engineering` secret scope.

---

## Prerequisites

Three things must be in place before the first notebook:

1. **Neo4j Spark Connector** installed as a cluster library on the dedicated cluster:
   ```
   org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
   ```

2. **Secret scope populated** — the `neo4j-graph-engineering` scope must contain keys `uri`, `username`, `password`, and `genie_space_id`. The demo owner populates these by running `automated/setup_secrets.sh`. Participants can also store their own credentials interactively by running `00_required_setup.ipynb`.

3. **Tables loaded** — `accounts`, `merchants`, `transactions`, `account_links`, and `account_labels` must exist in `graph-enriched-lakehouse.graph-enriched-schema`. The demo owner loads them with `automated/upload_and_create_tables.sh`.

---

## Notebook Sequence

### 00_required_setup.ipynb

Stores Neo4j credentials in the `neo4j-graph-engineering` Databricks secret scope and verifies the Aura connection. Run this on the dedicated cluster if the admin has not already populated the scope for you.

### 01_neo4j_ingest.ipynb

Reads the five Delta tables and writes them to Neo4j as a property graph. Creates `:Account` and `:Merchant` nodes, `TRANSACTED_WITH` (Account → Merchant) and `TRANSFERRED_TO` (Account → Account) relationships. Requires the dedicated cluster with the Neo4j Spark Connector.

### 02_aura_gds_guide.ipynb

Run in the **Neo4j Aura Workspace → Query tab** (not on Databricks). Walks through three GDS algorithms on the projected graph:

- **PageRank** — writes `risk_score` to each Account node
- **Louvain** — writes `community_id` to each Account node
- **Node Similarity** — writes `similarity_score` to each Account node

### 03_pull_gold_tables.ipynb

Reads the enriched Account nodes and similarity relationships back from Neo4j via the Spark Connector and writes three gold tables to Unity Catalog:

- `gold_accounts` — account metadata + `risk_score`, `community_id`, `similarity_score`
- `gold_account_similarity_pairs` — pairwise similarity scores
- `gold_fraud_ring_communities` — ring-level community aggregates

### 04_train_model.ipynb _(optional)_

Trains a baseline gradient-boosting classifier on tabular features and a graph-augmented classifier on all features. Both runs log to MLflow with AUC, precision, recall, F1, and ROC curves. The final cell translates the lift in fraud caught into an estimated dollar impact.

---

## Genie Demo Notebooks

These notebooks use **serverless compute** (no Neo4j Spark Connector required). Run them before and after the GDS pipeline to demonstrate the gap that graph enrichment closes.

### Before GDS

| Notebook | Gap confirmed |
|----------|---------------|
| `hub_detection_no_threshold.ipynb` | Genie returns whale accounts instead of ring captains when asked for fraud hubs. Top-20 precision ≤ 50%. |
| `community_structure_invisible.ipynb` | Genie returns bilateral pairs, not 100-account rings. Max ring coverage < 5%. |
| `merchant_overlap_volume_inflation.ipynb` | High-volume normal accounts dominate by raw merchant count; ring Jaccard signal is invisible. Same-ring fraction < 30%. |

### After GDS

`gds_enrichment_closes_gaps.ipynb` — runs all three checks against the after-GDS Genie Space and confirms each question resolves: top-20 precision > 70%, max ring coverage > 80%, same-ring fraction > 60%.

---

## Reference Material

- `GENIE_SETUP.md` — Genie Space instructions to paste into the Space, and column definitions for `fraud_risk_tier`, `risk_score`, `community_id`, and `similarity_score`.
- `aura_gds_guide.md` — step-by-step GDS algorithm guide for running in the Neo4j Aura Query tab.
- `GOLD_TABLE_ENRICHMENT.md` — description of the three gold tables and their columns.
- `diagrams/` — architecture diagrams for the workshop.
