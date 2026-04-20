# Automated Pipeline: Admin Setup and CLI Job Runner

This directory contains the one-time admin setup scripts and CLI-driven job runner for the graph enrichment pipeline. Use it to generate synthetic fraud data, load Delta tables into Unity Catalog, configure Databricks secrets, submit pipeline stages as unattended Jobs, and validate Genie Space quality after GDS runs. See the top-level [README](../README.md) for the full architecture overview.

The notebooks under `workshop/` push Delta Lake tables into Neo4j and pull enriched graph features back, but they require a live notebook kernel and manual execution. The scripts in `automated/` wrap that same logic as Databricks Python tasks that run unattended via the CLI.

```
┌─────────────────────────────────────────────────────────────────┐
│  Local machine, one-time setup                                  │
│                                                                 │
│  2. uv run setup/generate_data.py                               │
│       → data/  (5 CSVs + ground_truth.json)                     │
│  Optional diagnostic (regression check when tuning parameters): │
│    uv run diagnostics/verify_fraud_patterns.py                  │
│  3. ./upload_and_create_tables.sh                               │
│       → Unity Catalog: 5 managed Delta tables                   │
│  4. ./setup_secrets.sh                                          │
│       → Databricks secret scope: uri, username, password,       │
│         genie_space_id                                          │
│  5. uv run setup/provision_genie_spaces.py                      │
│       → Genie Spaces: before-GDS + after-GDS                    │
│  6. uv run python -m cli submit 01_genie_run_before.py          │
│       → BEFORE baseline logged (structural questions on         │
│         base tables; no graph labels yet)                       │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │  python -m cli submit
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databricks cluster                                             │
│                                                                 │
│  7. 02_neo4j_ingest.py                                          │
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
│  8. uv run validation/run_gds.py                                │
│       (runs locally; connects to Aura via graphdatascience)     │
│       PageRank        → risk_score on every :Account node       │
│       Louvain         → community_id on every :Account node     │
│       Node Similarity → similarity_score + :SIMILAR_TO rels     │
│  9. uv run validation/verify_gds.py                             │
│       verifies GDS outputs against ground_truth.json            │
└──────────────────────────┬──────────────────────────────────────┘
                           │  Neo4j Spark Connector
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databricks cluster                                             │
│                                                                 │
│  10. 03_pull_gold_tables.py                                     │
│        reads:  enriched :Account nodes + :SIMILAR_TO rels       │
│        writes: gold_accounts                                    │
│                gold_account_similarity_pairs                    │
│                gold_fraud_ring_communities                      │
│  11. 04_validate_gold_tables.py  (data-correctness gate)        │
│        6 checks against ground_truth.json; exits 1 on fail      │
│  12. 05_genie_run_after.py   (AFTER space, observation)         │
│        asks one question per category sampler; captures SQL     │
│        and rows returned; writes artifact to results volume     │
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
uv run setup/generate_data.py
```

Generates the synthetic fraud dataset and writes six files to `automated/data/`:
`accounts.csv`, `merchants.csv`, `transactions.csv`, `account_links.csv`, `account_labels.csv`, `ground_truth.json`.

### Optional: verify fraud patterns in generated data (local, pre-GDS)

```bash
uv run diagnostics/verify_fraud_patterns.py
```

Regression diagnostic for the four structural fraud properties (within-ring density, anchor-merchant visit rate, PageRank separation, Node Similarity ratio). Runs locally against the raw CSVs before any GDS run, so the checks are structural approximations derived from the graph topology of the generated data. Run this when tuning generator parameters or investigating a suspected data-generation regression. It is not part of the required setup sequence; downstream GDS checks in `validation/verify_gds.py` cover the same properties after the algorithms have executed.

### 3. Upload data and create tables

```bash
./upload_and_create_tables.sh
```

Uploads the five CSVs and `ground_truth.json` to the Unity Catalog Volume, applies `sql/schema.sql` to create all five base tables with Unity Catalog column-level comments, then loads data via `INSERT OVERWRITE`. Requires `DATABRICKS_WAREHOUSE_ID` in `automated/.env`.

Schema and data are separate by design:
- `sql/schema.sql` defines column types and Unity Catalog column descriptions (the contract Genie reads)
- `INSERT OVERWRITE` loads data without touching the schema; column comments survive every re-run
- `CREATE OR REPLACE TABLE` in `sql/schema.sql` is idempotent; no manual drop steps needed

The three gold tables (`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`) are created by `03_pull_gold_tables.py` on the cluster using `sql/gold_schema.sql` (uploaded alongside the job scripts), following the same DDL-first pattern.

### 4. Store credentials as Databricks secrets

```bash
./setup_secrets.sh --profile <USER-PROFILE>
```

Reads `automated/.env` and writes four secrets into the `neo4j-graph-engineering` scope: `uri`, `username`, `password`, and `genie_space_id` (from `GENIE_SPACE_ID_BEFORE`). Workshop participants can also store their own credentials interactively by running `workshop/00_required_setup.ipynb`.

### 5. Provision Genie Spaces

```bash
uv run setup/provision_genie_spaces.py
```

Idempotently configures both Genie Spaces defined in `automated/.env` (`GENIE_SPACE_ID_BEFORE` and `GENIE_SPACE_ID_AFTER`). For each space it replaces table identifiers, sample questions, and text instructions with the contract declared at the top of the script. Exits 1 if any space fails the post-update assertion.

### 6. Run BEFORE Genie

Runs three structural-discovery questions plus a teaser against the BEFORE space to capture the baseline before graph enrichment. For CLI submission details, see [Running Jobs](#running-jobs) below.

Upload the job scripts to your workspace before the first submit (required whenever scripts are added or renamed):

```bash
uv run python -m cli upload --all
```

Then submit:

```bash
uv run python -m cli submit 01_genie_run_before.py
```

The three structural questions are graded against `ground_truth.json`; the teaser is reported as not available on this catalog. Exits 0 and writes a JSON artifact to `RESULTS_VOLUME_DIR`.

| Case | Question | After-GDS criterion (BEFORE is expected to miss) |
|------|----------|----------------|
| `hub_detection` | "Are there accounts that seem to be the hub of a money movement network that are potentially fraudulent?" | top-20 precision > 0.70 |
| `community_structure` | "Find groups of accounts transferring money heavily among themselves." | max Louvain ring coverage > 0.80 |
| `merchant_overlap` | "Which pairs of accounts have visited the most merchants in common?" | same-ring fraction > 0.60 with ≥5 pairs |
| `teaser_portfolio` | "What share of accounts sits in communities flagged as ring candidates, broken out by region?" | not graded — reported as not available on this catalog |

## Running Jobs

All pipeline jobs are submitted as Databricks Python tasks using the same pattern from inside `automated/`:

```bash
uv run python -m cli submit <script>
```

The sections below each follow this pattern. Before submitting any script, upload the job scripts to your workspace:

```bash
# Upload all jobs/ scripts (and sql/gold_schema.sql) to your Databricks workspace
uv run python -m cli upload --all

# Inspect logs from the most recent run
uv run python -m cli logs

# Clean up workspace files and run history
uv run python -m cli clean --yes
```

### 7. Neo4j Ingest

Pushes the five Delta tables into Neo4j as a property graph.

```bash
uv run python -m cli submit 02_neo4j_ingest.py
```

What `02_neo4j_ingest.py` does:

1. Fetches Neo4j credentials from the Databricks secret scope (`NEO4J_SECRET_SCOPE`)
2. Clears all nodes and relationships (`MATCH (n) DETACH DELETE n`)
3. Writes `:Account` nodes: `accounts` LEFT JOIN `account_labels` on `account_id`
4. Writes `:Merchant` nodes
5. Creates uniqueness constraints on `:Account` and `:Merchant` (required for efficient relationship writes)
6. Writes `TRANSACTED_WITH` relationships: `transactions` (Account → Merchant)
7. Writes `TRANSFERRED_TO` relationships: `account_links` (Account → Account)
8. Prints node and relationship counts as verification

### 8. Run GDS Pipeline

Runs the three GDS algorithms against Neo4j Aura. Runs locally using the `graphdatascience` Python client; no Databricks cluster required.

```bash
uv run validation/run_gds.py
```

Writes `risk_score`, `community_id`, and `similarity_score` properties to every `:Account` node, and creates `:SIMILAR_TO` relationships. Run this after `02_neo4j_ingest.py` completes.

### 9. Verify GDS Outputs

Checks all five signal properties against ground truth and prints a summary report. Exits non-zero on any failure.

```bash
uv run validation/verify_gds.py
```

Confirms PageRank separation, Louvain ring coverage, and Node Similarity ratios. Run this after `run_gds.py` completes and before submitting `03_pull_gold_tables.py`.

### 10. Pull Gold Tables

Reads GDS features back from Neo4j and writes three enriched gold tables to Delta Lake:
`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.

```bash
uv run python -m cli submit 03_pull_gold_tables.py
```

### 11. Validate Gold Tables

Data-correctness gate. Run after `03_pull_gold_tables.py` and before `05_genie_run_after.py` to confirm the gold tables align with ground truth before the AFTER run.

```bash
uv run python -m cli submit 04_validate_gold_tables.py
```

Runs six checks against the three gold tables, joining against `ground_truth.json` from the UC Volume. All joins key on `account_id`, not `community_id`, which drifts across GDS runs.

1. `gold_fraud_ring_communities` has exactly 10 rows with `is_ring_candidate=true`
2. Each ring-candidate community is dominated by a single ground-truth ring covering ≥ 80% of its home ring
3. All ring-candidate communities have `member_count` BETWEEN 50 AND 200
4. `fraud_risk_tier='high'` covers ≥ 95% of the 1,000 ring-member accounts
5. For each ring-candidate community, `top_account_id` is a member of the dominant ring per `ground_truth.json`
6. In `gold_account_similarity_pairs`, `same_community=true` holds for ≥ 95% of pairs where both accounts are in the same ring per `ground_truth.json`

Writes a JSON artifact to `RESULTS_VOLUME_DIR`. Exits non-zero on any failure.

### 12. Run AFTER Genie

Picks one question from each of five category samplers against the AFTER space, captures the SQL and rows Genie returns, and writes a JSON artifact to `RESULTS_VOLUME_DIR`. No grading; compare the artifact against the BEFORE baseline from step 6.

```bash
uv run python -m cli submit 05_genie_run_after.py
```

```
# Run a subset of categories (e.g. portfolio and operational only)
# python -m cli submit 05_genie_run_after.py SAMPLERS=cat1_portfolio,cat4_operational
```

The AFTER runner picks one question from each sampler by default. Pass `SAMPLERS=` to select a subset. Each question runs up to `GENIE_TEST_RETRIES` times (default 2).

| Sampler | Category |
|---------|----------|
| `cat1_portfolio` | Portfolio composition over structural segments |
| `cat2_cohort` | Cohort comparisons across risk tiers |
| `cat3_community_rollup` | Rollups over ring-candidate communities |
| `cat4_operational` | Operational and investigator workload |
| `cat5_merchant` | Merchant-side questions |

## Validation scripts

Diagnostic scripts that validate each pipeline stage. Run directly (not via CLI) from inside `automated/`:

```bash
# Verify raw Neo4j connection
uv run validation/validate_neo4j.py

# Verify cluster state and required cluster libraries before submitting
uv run validation/validate_cluster.py

# Verify node/edge counts and graph structure after ingestion
uv run validation/validate_neo4j_graph.py

# Run GDS algorithms (writes risk_score, community_id, similarity_score)
uv run validation/run_gds.py

# Verify GDS outputs: prints a pass/fail summary report
uv run validation/verify_gds.py

# Diagnose Node Similarity scores and Jaccard ratios
uv run validation/diagnose_similarity.py
```

All validation scripts read credentials from `automated/.env`.

## Project structure

```
automated/
├── pyproject.toml              # uv project; all dependencies
├── .env.sample                 # config template; copy to .env, never commit .env
├── config.py                   # loads .env, exposes all tuning constants
├── upload_and_create_tables.sh # applies sql/schema.sql, uploads CSVs, loads Delta tables
├── setup_secrets.sh            # stores Neo4j credentials in Databricks secrets
├── genie_instructions.md       # instructions text embedded in Genie Spaces
├── data/                       # generated CSVs + ground_truth.json
├── logs/                       # local mirror of UC Volume artifacts
├── setup/                      # one-time local admin scripts (run before a demo)
│   ├── generate_data.py        # generates synthetic fraud dataset to data/
│   ├── provision_genie_spaces.py # idempotently configures before/after Genie Spaces
│   ├── checks_structural.py    # structural fraud-pattern check helpers for verify_fraud_patterns.py
│   ├── checks_genie_csv.py     # Genie CSV and GDS output check helpers for verify_fraud_patterns.py
│   └── report.py               # report rendering and JSON snapshot IO for verify_fraud_patterns.py
├── diagnostics/                # optional regression checks, not in required sequence
│   └── verify_fraud_patterns.py # checks structural properties of generated data
├── sql/                        # all DDL in one place
│   ├── schema.sql              # base table DDL with UC column comments
│   └── gold_schema.sql         # gold table DDL with UC column comments
├── cli/
│   ├── __init__.py             # Runner instantiation (scripts_dir="jobs")
│   └── __main__.py             # python -m cli entry point
├── jobs/                       # scripts submitted to Databricks via python -m cli submit
│   ├── 01_genie_run_before.py  # BEFORE space runner: 3 structural questions + teaser
│   ├── 02_neo4j_ingest.py      # push Delta tables into Neo4j as a property graph
│   ├── 03_pull_gold_tables.py  # pull GDS features back to Delta gold tables
│   ├── 04_validate_gold_tables.py # data-correctness gate for the three gold tables
│   ├── 05_genie_run_after.py   # AFTER space runner: one question per category sampler
│   ├── cat1_portfolio.py       # AFTER question bank: portfolio composition
│   ├── cat2_cohort.py          # AFTER question bank: cohort comparisons
│   ├── cat3_community_rollup.py # AFTER question bank: community rollups
│   ├── cat4_operational.py     # AFTER question bank: operational workload
│   ├── cat5_merchant.py        # AFTER question bank: merchant-side questions
│   ├── _cluster_bootstrap.py   # cluster bootstrap helpers (inject_params, resolve_here)
│   ├── _demo_utils.py          # Genie API + check helpers
│   ├── _genie_run_artifact.py  # shared artifact schema + loader for genie_run_*.json
│   ├── _gold_constants.py      # shared thresholds used by pull and validate
│   └── _neo4j_secrets.py       # loads Neo4j credentials from Databricks secret scope
└── validation/                 # local preflight and diagnostic scripts
    ├── _common.py              # shared helpers imported by validation scripts
    ├── validate_neo4j.py       # connection check
    ├── validate_cluster.py     # cluster state and required library check
    ├── validate_neo4j_graph.py # node/edge count and structure checks
    ├── run_gds.py              # runs GDS algorithms against Neo4j Aura
    ├── verify_gds.py           # verifies GDS outputs, prints summary report
    └── diagnose_similarity.py  # Jaccard ratio diagnostics
```
