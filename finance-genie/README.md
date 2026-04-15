# Graph-Augmented Intelligence — Databricks + Neo4j Aura

A four-notebook walkthrough showing how to enrich a Databricks fraud-detection
model with graph features computed in Neo4j Aura's Graph Data Science (GDS)
library. Data moves bidirectionally between Delta Lake and Neo4j via the
Neo4j Spark Connector; GDS algorithms (PageRank, Louvain, Node Similarity)
produce features that a baseline tabular model cannot.

The final notebook, `03_pull_and_model`, closes the loop by training two
`GradientBoostingClassifier` models on the same fraud label: a baseline fit
on tabular features only (balance, transaction aggregates, P2P counts,
encoded categoricals) and a graph-augmented model that adds the three
GDS-derived features (`risk_score`, `community_id`, `similarity_score`).
Both runs are logged to MLflow with AUC, precision, recall, and F1, then
compared head-to-head via ROC curves, confusion matrices, and feature
importance — translating the lift into an estimated dollar impact from the
additional fraud caught.

## Notebooks

| # | Notebook | Runs In | Purpose |
|---|----------|---------|---------|
| 00 | `00_setup_and_data.py` | Databricks | Generate a synthetic financial-transaction graph (accounts, merchants, transactions, P2P transfers) as Delta tables. A small fraction of accounts are planted as fraud rings. |
| 01 | `01_neo4j_ingest.py` | Databricks | Push Delta tables into Neo4j Aura as a typed property graph using the Neo4j Spark Connector. |
| 02 | `02_aura_gds_guide.py` | Neo4j Aura Workspace | Reference guide of Cypher + GDS commands to run in Aura: project the graph, run PageRank / Louvain / Node Similarity, write results back as node properties. Also available as plain markdown in [`aura_gds_guide.md`](./aura_gds_guide.md). |
| 03 | `03_pull_and_model.py` | Databricks | Read enriched Account nodes back via the Spark Connector, register graph features in Unity Catalog Feature Store, train a baseline vs graph-augmented model, and quantify the lift. |

## Quick Start

### 1. Prerequisites

- Databricks workspace (Unity Catalog enabled, serverless or a cluster with the Neo4j Spark Connector installed)
- A running Neo4j Aura instance with GDS enabled (AuraDS or Aura Plugin)
- Databricks CLI installed and authenticated locally

### 2. Configure secrets

Copy the sample env file and fill in your Aura credentials:

```bash
cp .env.sample .env
# edit .env with your NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD
```

Push them into the Databricks secret scope `neo4j-graph-engineering`:

```bash
./setup_secrets.sh
```

The notebooks read credentials via:

```python
dbutils.secrets.get("neo4j-graph-engineering", "uri")
dbutils.secrets.get("neo4j-graph-engineering", "username")
dbutils.secrets.get("neo4j-graph-engineering", "password")
```

### 3. Generate data and push to Neo4j (Databricks)

Import the four `.py` files into Databricks — they are saved in Databricks
notebook source format — then run the first two in order:

1. `00_setup_and_data` — builds the synthetic Delta tables (accounts,
   merchants, transactions, P2P transfers) with fraud rings planted.
2. `01_neo4j_ingest` — pushes those Delta tables into your Neo4j Aura
   instance as a typed property graph via the Neo4j Spark Connector.

### 4. Compute graph features in Aura

Switch to the **Neo4j Aura Workspace → Query tab** and walk through
`02_aura_gds_guide` to project the graph and run PageRank, Louvain, and
Node Similarity. The Cypher steps are also available as plain markdown in
[`aura_gds_guide.md`](./aura_gds_guide.md) if you prefer to follow along
outside a Databricks notebook.

When you're done, every Account node carries `risk_score`, `community_id`,
and `similarity_score` properties.

### 5. Pull features and train models (Databricks)

Back in Databricks, run `03_pull_and_model` to read the enriched Account
nodes via the Spark Connector, register the graph features in Unity
Catalog Feature Store, and train the baseline vs graph-augmented
`GradientBoostingClassifier` models — ending with a head-to-head lift
comparison and estimated fraud-savings impact.

## Unity Catalog Defaults

The notebooks create and use:

- Catalog: `graph_feature_engineering_demo`
- Schema: `neo4j_webinar`

Change the `CATALOG` / `SCHEMA` constants at the top of each notebook if you prefer a different location.
