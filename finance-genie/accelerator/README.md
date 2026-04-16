# Neo4j Ingest — Databricks Background Job

The notebook `01_neo4j_ingest.ipynb` pushes Delta Lake tables into Neo4j as a property graph but requires a live notebook kernel and manual execution. This accelerator wraps the same logic as a Databricks Python task that runs unattended as a background job.

```
┌──────────────────────────────────────────────────┐
│  Local machine (uv run python -m cli submit ...)  │
└────────────────────┬─────────────────────────────┘
                     │  Databricks Jobs API
                     ▼
┌──────────────────────────────────────────────────┐
│  Databricks cluster                              │
│  neo4j_ingest.py                                 │
│    reads:  accounts, account_labels, merchants,  │
│            transactions, account_links           │
│    writes: :Account, :Merchant nodes             │
│            TRANSACTED_WITH, TRANSFERRED_TO rels  │
└────────────────────┬─────────────────────────────┘
                     │  Neo4j Spark Connector
                     ▼
┌──────────────────────────────────────────────────┐
│  Neo4j (Aura or self-hosted)                     │
└──────────────────────────────────────────────────┘
```

## Prerequisites

- **Neo4j Spark Connector JAR** installed as a cluster library on the target cluster
- **Databricks secret scope** `neo4j-graph-engineering` with keys `uri`, `username`, `password`
- **uv** installed locally (`brew install uv` or `pip install uv`)

## Setup

Copy `.env.sample` to `.env` and fill in your cluster ID and workspace path:

```bash
cp .env.sample .env
```

```bash
DATABRICKS_PROFILE=azure-rk-knight
DATABRICKS_COMPUTE_MODE=cluster
DATABRICKS_CLUSTER_ID=0123-456789-abcdef
DATABRICKS_WORKSPACE_DIR=/Users/you@example.com/graph-enriched-lakehouse/accelerator

CATALOG=graph-enriched-lakehouse
SCHEMA=graph-enriched-schema
NEO4J_SECRET_SCOPE=neo4j-graph-engineering
```

`CATALOG`, `SCHEMA`, and `NEO4J_SECRET_SCOPE` are forwarded as parameters to the submitted script — override them here without touching the script.

## Usage

```bash
# Upload the script to your Databricks workspace
uv run python -m cli upload --all

# Submit and wait for completion (streams result state and run URL)
uv run python -m cli submit neo4j_ingest.py

# Inspect logs from the most recent run
uv run python -m cli logs

# Clean up workspace files and run history
uv run python -m cli clean --yes
```

## What the job does

1. Installs `graphdatascience` on the cluster at runtime
2. Fetches Neo4j credentials from the Databricks secret scope
3. Clears all nodes and relationships (`MATCH (n) DETACH DELETE n`)
4. Writes `:Account` nodes — `accounts` LEFT JOIN `account_labels` on `account_id`
5. Writes `:Merchant` nodes
6. Writes `TRANSACTED_WITH` relationships — `transactions` (Account → Merchant)
7. Writes `TRANSFERRED_TO` relationships — `account_links` (Account → Account)
8. Prints node and relationship counts as verification

## Project structure

```
accelerator/
├── pyproject.toml          # uv project; databricks-job-runner dependency
├── .env.sample             # config template — copy to .env, never commit .env
├── cli/
│   ├── __init__.py         # Runner instantiation
│   └── __main__.py         # python -m cli entry point
└── agent_modules/
    └── neo4j_ingest.py     # translated notebook logic, runs on Databricks
```
