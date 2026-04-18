# Automated Pipeline: Admin Setup and CLI Job Runner

This directory contains the one-time admin setup scripts and CLI-driven job runner for the graph enrichment pipeline. Use it to generate synthetic fraud data, load Delta tables into Unity Catalog, configure Databricks secrets, submit pipeline stages as unattended Jobs, and validate Genie Space quality after GDS runs. See the top-level [README](../README.md) for the full architecture overview.

The notebooks under `workshop/` push Delta Lake tables into Neo4j and pull enriched graph features back, but they require a live notebook kernel and manual execution. The scripts in `automated/` wrap that same logic as Databricks Python tasks that run unattended via the CLI.

```
┌─────────────────────────────────────────────────────────────────┐
│  Local machine — one-time setup                                 │
│                                                                 │
│  1. uv run generate_data.py                                     │
│       → data/  (5 CSVs + ground_truth.json)                     │
│  2. uv run verify_fraud_patterns.py                             │
│       → validates 4 structural fraud properties                 │
│  3. ./upload_and_create_tables.sh                               │
│       → Unity Catalog: 5 managed Delta tables                   │
│  4. ./setup_secrets.sh                                          │
│       → Databricks secret scope: uri, username, password,       │
│         genie_space_id                                          │
│  5. uv run provision_genie_spaces.py                            │
│       → Genie Spaces: before-GDS + after-GDS                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │  python -m cli submit
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databricks cluster                                             │
│                                                                 │
│  6. neo4j_ingest.py                                             │
│       reads:  accounts, account_labels, merchants,              │
│               transactions, account_links                       │
│       writes: :Account + :Merchant nodes                        │
│               TRANSACTED_WITH + TRANSFERRED_TO rels             │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Neo4j Spark Connector
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Neo4j Aura                                                     │
│                                                                 │
│  7. uv run validation/run_and_verify_gds.py                     │
│       (runs locally; connects to Aura via graphdatascience)     │
│       PageRank        → risk_score on every :Account node       │
│       Louvain         → community_id on every :Account node     │
│       Node Similarity → similarity_score + :SIMILAR_TO rels     │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Neo4j Spark Connector
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databricks cluster                                             │
│                                                                 │
│  8.  pull_gold_tables.py                                        │
│        reads:  enriched :Account nodes + :SIMILAR_TO rels       │
│        writes: gold_accounts                                    │
│                gold_account_similarity_pairs                    │
│                gold_fraud_ring_communities                      │
│  9.  validate_gold_tables.py  (data-correctness gate)           │
│        6 checks against ground_truth.json — exits 1 on fail     │
│  10. genie_run_before.py  (BEFORE space — observation)          │
│        logs 3 questions against base-table-only space           │
│  11. genie_run_after.py   (AFTER space — observation)           │
│        logs 3 questions against gold-table-enriched space       │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Neo4j Spark Connector JAR** installed as a cluster library:
  `org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3`
- **graphdatascience** installed as a cluster library (PyPI)
- **Databricks secret scope** `neo4j-graph-engineering` with keys `uri`, `username`, `password`, `genie_space_id`
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

### 6. Provision Genie Spaces

```bash
uv run provision_genie_spaces.py
```

Idempotently configures both Genie Spaces defined in `automated/.env` (`GENIE_SPACE_ID_BEFORE` and `GENIE_SPACE_ID_AFTER`). For each space it replaces table identifiers, sample questions, and text instructions with the contract declared at the top of the script. Exits 1 if any space fails the post-update assertion.

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

### GDS pipeline — `run_and_verify_gds.py`

Runs the three GDS algorithms against Neo4j Aura and verifies their outputs. Runs locally using the `graphdatascience` Python client; no Databricks cluster required.

```bash
uv run validation/run_and_verify_gds.py
```

Writes `risk_score`, `community_id`, and `similarity_score` properties to every `:Account` node, and creates `:SIMILAR_TO` relationships. Also runs a diagnostic suite confirming PageRank separation, Louvain ring coverage, and Node Similarity ratios. Run this after `neo4j_ingest.py` completes and before submitting `pull_gold_tables.py`.

### `pull_gold_tables.py`

Reads GDS features back from Neo4j and writes three enriched gold tables to Delta Lake:
`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.

```bash
uv run python -m cli submit pull_gold_tables.py
```

### `validate_gold_tables.py`

Data-correctness gate. Run after `pull_gold_tables.py` and before `genie_test.py` to confirm the gold tables align with ground truth before running Genie tests.

```bash
uv run python -m cli submit validate_gold_tables.py
```

### `genie_run.py`

Parameterized Genie runner — runs the same three analyst-phrased questions against any Genie Space, records results, and writes a JSON artifact to `RESULTS_VOLUME_DIR`. No pass/fail gating by default. See [Automated Genie testing](#automated-genie-testing).

Use the thin submit wrappers below — the CLI runner passes parameters from `.env`, so each wrapper resolves `GENIE_SPACE_ID_BEFORE` / `GENIE_SPACE_ID_AFTER` and sets the correct label before delegating to `genie_run.main()`.

```bash
# BEFORE space (base tables only)
uv run python -m cli submit genie_run_before.py

# AFTER space (base + gold tables)
uv run python -m cli submit genie_run_after.py

# Optional — reproduce legacy gating behavior (exits non-zero if thresholds not met)
# Add GATE=true to .env, submit genie_run_after.py, then remove it from .env
```

### `compare_genie_runs.py`

Local script that auto-discovers the most recent BEFORE and AFTER run artifacts from `RESULTS_VOLUME_DIR`, downloads them, and emits a markdown side-by-side comparison report. Run this after both `genie_run.py` submissions complete.

```bash
# Auto-discover latest before + after artifacts
uv run compare_genie_runs.py

# Or replay against specific historical artifacts
uv run compare_genie_runs.py \
    --before-path /Volumes/.../genie_run_before_2026-04-18T17-00-00Z.json \
    --after-path  /Volumes/.../genie_run_after_2026-04-18T17-10-00Z.json
```

Writes the report to `automated/logs/compare_<timestamp>.md` and prints an E2E summary line:
`E2E PASS — 8/8 steps green, 6/6 Genie questions returned data`

## What `neo4j_ingest.py` does

1. Fetches Neo4j credentials from the Databricks secret scope (`NEO4J_SECRET_SCOPE`)
2. Clears all nodes and relationships (`MATCH (n) DETACH DELETE n`)
3. Writes `:Account` nodes: `accounts` LEFT JOIN `account_labels` on `account_id`
4. Writes `:Merchant` nodes
5. Creates uniqueness constraints on `:Account` and `:Merchant` (required for efficient relationship writes)
6. Writes `TRANSACTED_WITH` relationships: `transactions` (Account → Merchant)
7. Writes `TRANSFERRED_TO` relationships: `account_links` (Account → Account)
8. Prints node and relationship counts as verification

## What `validate_gold_tables.py` does

Runs six checks against the three gold tables, joining against `ground_truth.json` from the UC Volume. All joins key on `account_id`, not `community_id`, which drifts across GDS runs.

1. `gold_fraud_ring_communities` has exactly 10 rows with `is_ring_candidate=true`
2. Each ring-candidate community is dominated by a single ground-truth ring covering ≥ 80% of its home ring
3. All ring-candidate communities have `member_count` BETWEEN 50 AND 200
4. `fraud_risk_tier='high'` covers ≥ 75% of the 1,000 ring-member accounts
5. For each ring-candidate community, `top_account_id` is a member of the dominant ring per `ground_truth.json`
6. In `gold_account_similarity_pairs`, `same_community=true` holds for ≥ 95% of pairs where both accounts are in the same ring per `ground_truth.json`

Writes a JSON artifact to `RESULTS_VOLUME_DIR`. Exits non-zero on any failure.

## Automated Genie testing

`agent_modules/genie_run.py` runs three analyst-phrased questions against any Genie Space, records the SQL Genie generated and the rows it returned, and writes a JSON artifact to `RESULTS_VOLUME_DIR`. By default it exits 0 as long as Genie responds — no pass/fail gating. Use `GATE=true` to reproduce the legacy CI-gate behavior.

### Questions (same for both spaces)

| Case | Question | After-GDS threshold (observation; gate under `GATE=true`) |
|------|----------|----------------|
| `hub_detection` | "Are there accounts that seem to be the hub of a money movement network that are potentially fraudulent?" | top-20 precision > 0.70 |
| `community_structure` | "Find groups of accounts transferring money heavily among themselves." | max Louvain ring coverage > 0.80 |
| `merchant_overlap` | "Which pairs of accounts have visited the most merchants in common?" | same-ring fraction > 0.60 |

Both the BEFORE (base-table-only) and AFTER (gold-table-enriched) spaces receive the same questions. The demo narrative holds because the gold tables are designed to answer these analyst-phrased questions well; the base tables are not.

### Sample output (`GATE=false`, default)

```
==============================================================
Genie run — 2026-04-18T17:05:22Z
Space: 01f13926c98315898f217625c525f8fb  Label: before
GATE=false (observation only)
==============================================================
  hub_detection      RESPONDED  precision=0.43  criterion=> 0.70
  community_structure  RESPONDED  max_ring_coverage=0.02  criterion=> 0.80
  merchant_overlap   RESPONDED  same_ring_fraction=0.08  criterion=> 0.60
--------------------------------------------------------------
Responded: 3/3

Artifact: /Volumes/.../genie_test_results/genie_run_before_2026-04-18T17-05-22Z.json
```

Each question runs up to `GENIE_TEST_RETRIES` times (default 2). Under `GATE=true`, the job exits non-zero if any after-GDS threshold is not met.

## Validation scripts

Diagnostic scripts that validate each pipeline stage. Run directly (not via CLI) from inside `automated/`:

```bash
# Verify raw Neo4j connection
uv run validation/validate_neo4j.py

# Verify cluster state and required cluster libraries before submitting
uv run validation/validate_cluster.py

# Verify node/edge counts and graph structure after ingestion
uv run validation/validate_neo4j_graph.py

# Run GDS algorithms against Neo4j Aura and verify outputs
# Also the pipeline step between neo4j_ingest.py and pull_gold_tables.py
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
├── provision_genie_spaces.py   # idempotently configures before/after Genie Spaces
├── compare_genie_runs.py       # compares before/after artifacts, emits markdown report
├── genie_instructions.md       # instructions text embedded in Genie Spaces
├── data/                       # generated CSVs + ground_truth.json
├── logs/                       # local mirror of UC Volume artifacts + compare reports
├── cli/
│   ├── __init__.py             # Runner instantiation
│   └── __main__.py             # python -m cli entry point
├── agent_modules/              # scripts submitted to Databricks (name is fixed)
│   ├── neo4j_ingest.py         # push Delta tables into Neo4j as a property graph
│   ├── pull_gold_tables.py     # pull GDS features back to Delta gold tables
│   ├── validate_gold_tables.py # data-correctness gate for the three gold tables
│   ├── genie_run.py            # parameterized Genie runner (core logic)
│   ├── genie_run_before.py     # submit wrapper — targets GENIE_SPACE_ID_BEFORE
│   ├── genie_run_after.py      # submit wrapper — targets GENIE_SPACE_ID_AFTER
│   ├── demo_utils.py           # Genie API + check helpers
│   ├── gold_constants.py       # shared thresholds used by pull and validate
│   └── neo4j_secrets.py        # loads Neo4j credentials from Databricks secret scope
└── validation/
    ├── validate_neo4j.py        # connection check
    ├── validate_cluster.py      # cluster state and required library check
    ├── validate_neo4j_graph.py  # node/edge count and structure checks
    ├── run_and_verify_gds.py    # runs GDS pipeline and verifies outputs
    └── diagnose_similarity.py   # Jaccard ratio diagnostics
```
