# Workshop Guide

This workshop is the hands-on notebook path for the Finance Genie graph
enrichment demo. It is aligned with the `demo-guide/` narrative, but it is a
separate executable asset. Each notebook maps to a live demo stage: the
**Anchor** (one fraud question, two answers) runs in Genie; the **Pipeline**
(load, enrich, land in Gold) runs as three Databricks notebooks. Same
Databricks catalog, same Genie, new dimensions. The enrichment pipeline runs
Neo4j GDS as a silver-to-gold stage that writes community membership, risk
centrality, and structural similarity back as scalar columns.

**Same Databricks spend. Strictly more answers.**

**Audience:** Workshop participants running the demo interactively on Databricks.

**Prerequisite state:** The demo owner has already run the `enrichment-pipeline/` setup
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
   `enrichment-pipeline/setup_secrets.sh`. Participants can also store them interactively
   by running `00_required_setup.ipynb`.

3. **Tables loaded:** `accounts`, `merchants`, `transactions`, `account_links`,
   and `account_labels` must exist in
   `graph-on-databricks.graph-enriched-schema`. The demo owner loads them
   with `enrichment-pipeline/upload_and_create_tables.sh`.

---

## Notebook Sequence

The notebooks are grouped by which slide section they support. A workshop
participant following along with the deck can jump between slide and notebook
without losing the thread.

### Demo prep

**`00_required_setup.ipynb`** — Stores Neo4j credentials and both Genie Space
IDs in the `neo4j-graph-engineering` Databricks secret scope, then verifies
the Aura connection. Run once on the dedicated cluster if the admin has not
already populated the scope.

### Anchor section (slides 6–7, plus validations)

**`01_genie_silver_questions.ipynb`** *(serverless)* — Runs the before/after
reveal live against both Genie Spaces. A tabular warm-up confirms Genie is
working. An analytics challenge shows it handling joins and conditional
aggregates correctly. Then three anchor before/after pairs run side by side —
merchant favorites, book share, and investigator review queue — followed by
two validation pairs (merchant ring-candidate share; high-volume account
community membership). The gap between each before and after answer is the
argument for the enrichment pipeline.

### Pipeline section (slides 12–14)

Three notebooks that convert network topology into catalog columns. Each
maps to one step on the "Enrichment Pipeline" slide.

**`02_neo4j_ingest.ipynb`** *(dedicated cluster)* — **Load Silver into Neo4j.**
Reads the five Delta tables and writes them to Neo4j as a property graph:
`:Account` and `:Merchant` nodes, `TRANSACTED_WITH` (Account → Merchant) and
`TRANSFERRED_TO` (Account → Account) relationships.

**`03_gds_enrichment.ipynb`** *(dedicated cluster)* — **Run GDS, patterns
become columns.** Runs three GDS algorithms via the `graphdatascience` Python
client and writes the results back to each Account node:
- **PageRank** → `risk_score` (centrality in the transfer network)
- **Louvain** → `community_id` (each fraud ring becomes one community)
- **Node Similarity** → `similarity_score` (Jaccard overlap of shared-merchant sets)

**`04_pull_gold_tables.ipynb`** *(dedicated cluster)* — **Enrich, results land
in Gold.** Reads the enriched Account nodes and similarity relationships back
from Neo4j and writes three Gold tables to Unity Catalog. These are what the
AFTER Genie space queries.
- **`gold_accounts`** — account metadata plus `risk_score`, `community_id`,
  `similarity_score`, community aggregates (`community_size`,
  `community_avg_risk_score`, `community_risk_rank`, `inbound_transfer_events`),
  and the derived flags `is_ring_community` and `fraud_risk_tier`
- **`gold_account_similarity_pairs`** — pairwise similarity scores with a
  `same_community` flag
- **`gold_fraud_ring_communities`** — one row per Louvain community with
  `member_count`, `avg_risk_score`, `avg_similarity_score`,
  `is_ring_candidate`, and `top_account_id`

### Off the 15-minute demo path

**`06_train_model.ipynb`** *(optional)* — Supplementary. Not part of the
live demo flow. Trains a baseline gradient-boosting classifier on tabular
features and a graph-augmented classifier on tabular plus
`risk_score` / `community_id` / `similarity_score`, logs both runs to MLflow,
and translates the lift into estimated dollar impact. Useful for ML-focused
Q&A; skip for the analyst-workflow demo.

---

## Reference Material

- `genie-guide.md` — copy-paste questions organized as Primary Anchor,
  Backup Anchor, Validation Pairs, Extended Questions, and Fill-In / Q&A
- `GENIE_SETUP.md` — pointer file that explains where the live Genie Space
  configuration comes from (`enrichment-pipeline/setup/provision_genie_spaces.py` +
  `enrichment-pipeline/genie_instructions.md` + UC column comments), plus the
  workshop-specific before/after narrative for the "hub of a money
  movement network" question
- `aura_gds_guide.md` — step-by-step GDS algorithm guide for running in the
  Neo4j Aura Query tab, an alternative to the Python-client notebook
- `diagrams/` — architecture diagrams for the workshop
