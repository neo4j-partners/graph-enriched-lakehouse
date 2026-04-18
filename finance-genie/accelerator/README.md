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

## Automated Genie testing

`agent_modules/genie_test.py` automates the three validation questions from `genie_demos/gds_enrichment_closes_gaps.ipynb` so you can iterate on a Genie Space's **Instructions** field and get pass/fail feedback in one command instead of re-running a notebook.

### What it checks

| Case | Question | Pass criterion |
|------|----------|----------------|
| `hub_detection` | "Which accounts have the highest fraud risk based on their transfer network position?" | top-20 precision > 0.70 |
| `community_structure` | "Find groups of accounts that form suspicious transaction communities based on their transfer patterns." | max Louvain ring coverage > 0.80 |
| `similarity_pairs` | "Which pairs of accounts share the most similar merchant visit patterns?" | top same-ring fraction > 0.60 |

Each question runs up to `GENIE_TEST_RETRIES` times (default 2). The check functions live in `agent_modules/demo_utils.py`, a project-local trim of `genie_demos/demo_utils.py` scoped to the three after-GDS checks this runner uses.

### Additional `.env` keys

```bash
GENIE_SPACE_ID_BEFORE=<before-gds-genie-space-id>
GENIE_SPACE_ID_AFTER=<after-gds-genie-space-id>
GROUND_TRUTH_PATH=/Volumes/<catalog>/<schema>/<volume>/ground_truth.json
RESULTS_VOLUME_DIR=/Volumes/<catalog>/<schema>/<volume>/genie_test_results
GENIE_TEST_RETRIES=2
GENIE_TEST_TIMEOUT_SECONDS=120
```

The `RESULTS_VOLUME_DIR` must exist before the first run. Create it with:

```bash
uv run python -m cli volume create <catalog>.<schema>.<volume>
```

### Usage

```bash
uv run python -m cli upload --all
uv run python -m cli submit genie_test.py
uv run python -m cli logs
```

Sample output:

```
============================================================
Genie test run — 2026-04-16T14:32:10Z
Space: 01abc...
============================================================
  hub_detection          PASS   precision=0.85             attempt=1/2
  community_structure    FAIL   max_ring_coverage=0.52     attempt=2/2
  similarity_pairs       PASS   same_ring_fraction=0.70    attempt=1/2
------------------------------------------------------------
PASSED: 2   FAILED: 1
Artifact: /Volumes/.../genie_test_results/genie_test_2026-04-16T14-32-10Z.json
```

The job exits non-zero if any check fails, and writes a full JSON artifact (including Genie SQL, row counts, and a preview of returned rows) to `RESULTS_VOLUME_DIR` for later inspection.

## Project structure

```
accelerator/
├── pyproject.toml          # uv project; databricks-job-runner dependency
├── .env.sample             # config template — copy to .env, never commit .env
├── cli/
│   ├── __init__.py         # Runner instantiation
│   └── __main__.py         # python -m cli entry point
└── agent_modules/
    ├── neo4j_ingest.py     # translated notebook logic, runs on Databricks
    ├── genie_test.py       # automated Genie Space test runner
    └── demo_utils.py       # Genie API + check helpers used by genie_test.py
```
