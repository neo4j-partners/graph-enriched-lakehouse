# Neo4j Ingest — Databricks Background Jobs

The notebooks under `workshop/` push Delta Lake tables into Neo4j and pull enriched graph features back, but they require a live notebook kernel and manual execution. The scripts in `automated/` wrap that same logic as Databricks Python tasks that run unattended via the CLI.

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

- **Neo4j Spark Connector JAR** installed as a cluster library:
  `org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3`
- **graphdatascience** installed as a cluster library (PyPI)
- **Databricks secret scope** `neo4j-graph-engineering` with keys `uri`, `username`, `password`
- **uv** installed locally (`brew install uv` or `pip install uv`)

Run `validation/validate_cluster.py` to confirm the cluster is ready before submitting any job.

## One-time admin setup

Run these steps from inside `automated/` before workshop participants use the notebooks.

### 1. Configure `.env`

```bash
cp .env.sample .env
```

Edit `.env` and fill in all placeholder values. `.env.sample` documents every key.

### 2. Generate synthetic data

```bash
uv run generate_data.py
```

Generates the synthetic fraud dataset and writes six files to `automated/data/`:
`accounts.csv`, `merchants.csv`, `transactions.csv`, `account_links.csv`, `account_labels.csv`, `ground_truth.json`.

### 3. Verify fraud patterns

```bash
uv run verify_fraud_patterns.py
```

Checks four structural properties the demo depends on: within-ring density ratio, anchor-merchant visit rate, PageRank separation, and Node Similarity ratio. All four must pass before loading data to Databricks.

### 4. Upload data and create tables

```bash
./upload_and_create_tables.sh
```

Uploads the five CSVs and `ground_truth.json` to the Unity Catalog Volume, then creates five managed Delta tables in `graph-enriched-lakehouse.graph-enriched-schema`. Requires `DATABRICKS_WAREHOUSE_ID` in `automated/.env`. The script is idempotent: it drops and recreates base tables on each run without touching gold tables.

### 5. Store credentials as Databricks secrets

```bash
./setup_secrets.sh --profile azure-rk-knight
```

Reads `automated/.env` and writes four secrets into the `neo4j-graph-engineering` scope: `uri`, `username`, `password`, and `genie_space_id` (from `GENIE_SPACE_ID_BEFORE`). Workshop participants can also store their own credentials interactively by running `workshop/00_required_setup.ipynb`.

## Running jobs

All CLI commands are run from inside `automated/`:

```bash
# Upload all agent_modules scripts to your Databricks workspace
uv run python -m cli upload --all

# Submit a script and stream its result state and run URL
uv run python -m cli submit <script>

# Inspect logs from the most recent run
uv run python -m cli logs

# Clean up workspace files and run history
uv run python -m cli clean --yes
```

### `neo4j_ingest.py`

Pushes the five Delta tables into Neo4j as a property graph.

```bash
uv run python -m cli submit neo4j_ingest.py
```

### `pull_gold_tables.py`

Reads GDS features back from Neo4j and writes three enriched gold tables to Delta Lake:
`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.

```bash
uv run python -m cli submit pull_gold_tables.py
```

### `genie_test.py` / `genie_test_before.py`

Automated Genie Space test runners. See [Automated Genie testing](#automated-genie-testing).

```bash
uv run python -m cli submit genie_test.py
uv run python -m cli submit genie_test_before.py
```

## What `neo4j_ingest.py` does

1. Fetches Neo4j credentials from the Databricks secret scope (`NEO4J_SECRET_SCOPE`)
2. Clears all nodes and relationships (`MATCH (n) DETACH DELETE n`)
3. Writes `:Account` nodes — `accounts` LEFT JOIN `account_labels` on `account_id`
4. Writes `:Merchant` nodes
5. Creates uniqueness constraints on `:Account` and `:Merchant` (required for efficient relationship writes)
6. Writes `TRANSACTED_WITH` relationships — `transactions` (Account → Merchant)
7. Writes `TRANSFERRED_TO` relationships — `account_links` (Account → Account)
8. Prints node and relationship counts as verification

## Automated Genie testing

`agent_modules/genie_test.py` automates the three validation questions from `workshop/gds_enrichment_closes_gaps.ipynb` so you can iterate on a Genie Space's **Instructions** field and get pass/fail feedback in one command instead of re-running a notebook.

`agent_modules/genie_test_before.py` runs the same questions against the pre-enrichment Genie Space to confirm that the three fraud-detection questions *cannot* be answered accurately using only the raw base tables.

### What `genie_test.py` checks (after GDS)

| Case | Question | Pass criterion |
|------|----------|----------------|
| `hub_detection` | "Which accounts have the highest fraud risk based on their transfer network position?" | top-20 precision > 0.70 |
| `community_structure` | "Find groups of accounts that form suspicious transaction communities based on their transfer patterns." | max Louvain ring coverage > 0.80 |
| `similarity_pairs` | "Which pairs of accounts share the most similar merchant visit patterns?" | top same-ring fraction > 0.60 |

### What `genie_test_before.py` checks (before GDS)

| Case | Question | Pass criterion |
|------|----------|----------------|
| `hub_detection` | Same as above | top-20 precision ≤ 0.50 (whale/fraud indistinguishable) |
| `community_structure` | Same as above | max ring coverage < 0.05 (pairs returned, not rings) |
| `merchant_overlap` | "Which pairs of accounts share the most similar merchant visit patterns?" | same-ring fraction < 0.30 (volume inflation dominates) |

Each question runs up to `GENIE_TEST_RETRIES` times (default 2). The job exits non-zero if any check fails, and writes a JSON artifact to `RESULTS_VOLUME_DIR`.

### Sample output

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

## Validation scripts

Diagnostic scripts that validate each pipeline stage. Run directly (not via CLI) from inside `automated/`:

```bash
# Verify raw Neo4j connection
uv run validation/validate_neo4j.py

# Verify cluster state and required cluster libraries before submitting
uv run validation/validate_cluster.py

# Verify node/edge counts and graph structure after ingestion
uv run validation/validate_neo4j_graph.py

# Run GDS algorithms locally against Neo4j Aura and verify outputs
uv run validation/run_and_verify_gds.py

# Diagnose Node Similarity scores and Jaccard ratios
uv run validation/diagnose_similarity.py
```

All validation scripts read credentials from `automated/.env`.

## Project structure

```
automated/
├── pyproject.toml              # uv project; all dependencies
├── .env.sample                 # config template — copy to .env, never commit .env
├── config.py                   # loads .env, exposes CONFIG dict
├── generate_data.py            # generates synthetic fraud dataset to data/
├── verify_fraud_patterns.py    # checks structural properties of generated data
├── upload_and_create_tables.sh # uploads CSVs and creates Delta tables
├── setup_secrets.sh            # stores Neo4j credentials in Databricks secrets
├── data/                       # generated CSVs + ground_truth.json
├── cli/
│   ├── __init__.py             # Runner instantiation
│   └── __main__.py             # python -m cli entry point
├── agent_modules/              # scripts submitted to Databricks (name is fixed)
│   ├── neo4j_ingest.py         # push Delta tables into Neo4j as a property graph
│   ├── pull_gold_tables.py     # pull GDS features back to Delta gold tables
│   ├── genie_test.py           # Genie test runner (after GDS enrichment)
│   ├── genie_test_before.py    # Genie test runner (before GDS enrichment)
│   └── demo_utils.py           # Genie API + check helpers
└── validation/
    ├── validate_neo4j.py        # connection check
    ├── validate_cluster.py      # cluster state and required library check
    ├── validate_neo4j_graph.py  # node/edge count and structure checks
    ├── run_and_verify_gds.py    # runs GDS pipeline and verifies outputs
    └── diagnose_similarity.py   # Jaccard ratio diagnostics
```
