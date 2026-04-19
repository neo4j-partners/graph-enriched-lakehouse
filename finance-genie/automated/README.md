# Automated Pipeline: Admin Setup and CLI Job Runner

This directory contains the one-time admin setup scripts and CLI-driven job runner for the graph enrichment pipeline. Use it to generate synthetic fraud data, load Delta tables into Unity Catalog, configure Databricks secrets, submit pipeline stages as unattended Jobs, and validate Genie Space quality after GDS runs. See the top-level [README](../README.md) for the full architecture overview.

The notebooks under `workshop/` push Delta Lake tables into Neo4j and pull enriched graph features back, but they require a live notebook kernel and manual execution. The scripts in `automated/` wrap that same logic as Databricks Python tasks that run unattended via the CLI.

One of the goals of this project is to show that even with fairly in-depth guidance toward the enriched data in the gold tables, Genie still does not always find the fraud — because the SQL Genie generates is non-deterministic, so the fraud it surfaces is mixed run-to-run. For example, in one AFTER run Genie read "the pairs of accounts that have visited the most merchants in common" as a strict superlative and emitted `RANK() OVER (ORDER BY similarity_score DESC) ... WHERE rnk = 1`, returning only 4 pairs tied at `similarity_score=0.5`. All 4 were same-ring, spanning 2 distinct fraud rings — real signal, but a much thinner sample than the AFTER sample output below (`ORDER BY similarity_score DESC LIMIT 100`, 100 pairs across 10 rings). Same question, same space, same gold tables; different SQL shape, different verdict. This non-determinism is the point the demo is designed to expose.

```
┌─────────────────────────────────────────────────────────────────┐
│  Local machine — one-time setup                                 │
│                                                                 │
│  1. uv run setup/generate_data.py                               │
│       → data/  (5 CSVs + ground_truth.json)                     │
│  2. ./upload_and_create_tables.sh                               │
│       → Unity Catalog: 5 managed Delta tables                   │
│  3. ./setup_secrets.sh                                          │
│       → Databricks secret scope: uri, username, password,       │
│         genie_space_id                                          │
│  4. uv run setup/provision_genie_spaces.py                      │
│       → Genie Spaces: before-GDS + after-GDS                    │
│                                                                 │
│  Optional diagnostic (regression check when tuning parameters): │
│    uv run diagnostics/verify_fraud_patterns.py                  │
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
│  7. uv run validation/run_gds.py                                │
│       (runs locally; connects to Aura via graphdatascience)     │
│       PageRank        → risk_score on every :Account node       │
│       Louvain         → community_id on every :Account node     │
│       Node Similarity → similarity_score + :SIMILAR_TO rels     │
│     uv run validation/verify_gds.py                             │
│       verifies GDS outputs against ground_truth.json            │
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
uv run setup/generate_data.py
```

Generates the synthetic fraud dataset and writes six files to `automated/data/`:
`accounts.csv`, `merchants.csv`, `transactions.csv`, `account_links.csv`, `account_labels.csv`, `ground_truth.json`.

### 3. Upload data and create tables

```bash
./upload_and_create_tables.sh
```

Uploads the five CSVs and `ground_truth.json` to the Unity Catalog Volume, applies `sql/schema.sql` to create all five base tables with Unity Catalog column-level comments, then loads data via `INSERT OVERWRITE`. Requires `DATABRICKS_WAREHOUSE_ID` in `automated/.env`.

Schema and data are separate by design:
- `sql/schema.sql` defines column types and Unity Catalog column descriptions (the contract Genie reads)
- `INSERT OVERWRITE` loads data without touching the schema — column comments survive every re-run
- `CREATE OR REPLACE TABLE` in `sql/schema.sql` is idempotent; no manual drop steps needed

The three gold tables (`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`) are created by `pull_gold_tables.py` on the cluster using `sql/gold_schema.sql` (uploaded alongside the job scripts), following the same DDL-first pattern.

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

### Optional: verify fraud patterns

```bash
uv run diagnostics/verify_fraud_patterns.py
```

Regression diagnostic for the four structural fraud properties (within-ring density, anchor-merchant visit rate, PageRank separation, Node Similarity ratio). Run this when tuning generator parameters or investigating a suspected data-generation regression. It is not part of the required setup sequence; downstream GDS checks in `validation/verify_gds.py` cover the same properties after the algorithms have executed.

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

### Neo4j Ingest

Pushes the five Delta tables into Neo4j as a property graph.

```bash
uv run python -m cli submit neo4j_ingest.py
```

### Run GDS Pipeline

Runs the three GDS algorithms against Neo4j Aura. Runs locally using the `graphdatascience` Python client; no Databricks cluster required.

```bash
uv run validation/run_gds.py
```

Writes `risk_score`, `community_id`, and `similarity_score` properties to every `:Account` node, and creates `:SIMILAR_TO` relationships. Run this after `neo4j_ingest.py` completes.

### Verify GDS Outputs

Checks all five signal properties against ground truth and prints a summary report. Exits non-zero on any failure.

```bash
uv run validation/verify_gds.py
```

Confirms PageRank separation, Louvain ring coverage, and Node Similarity ratios. Run this after `run_gds.py` completes and before submitting `pull_gold_tables.py`.

### Pull Gold Tables

Reads GDS features back from Neo4j and writes three enriched gold tables to Delta Lake:
`gold_accounts`, `gold_account_similarity_pairs`, `gold_fraud_ring_communities`.

```bash
uv run python -m cli submit pull_gold_tables.py
```

### Validate Gold Tables

Data-correctness gate. Run after `pull_gold_tables.py` and before `genie_run_before.py` to confirm the gold tables align with ground truth before running Genie tests.

```bash
uv run python -m cli submit validate_gold_tables.py
```

### Genie Runs

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

### BEFORE vs AFTER Comparison

The side-by-side markdown comparison is folded into `genie_run_after.py`. When `BEFORE_ARTIFACT` is set in `.env`, the wrapper reads both artifacts from the UC Volume after the AFTER run completes and prints the comparison report to stdout (visible in the job run log). The CLI runner forwards `BEFORE_ARTIFACT` to the job as a `KEY=VALUE` parameter alongside the rest of `.env`.

```bash
# Add the BEFORE artifact path to .env, then submit the AFTER run:
#   BEFORE_ARTIFACT=/Volumes/.../genie_run_before_2026-04-18T17-00-00Z.json
uv run python -m cli submit genie_run_after.py
```

When `BEFORE_ARTIFACT` is unset, the wrapper prints a one-line note explaining how to add it — the AFTER run itself still completes normally.

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
4. `fraud_risk_tier='high'` covers ≥ 95% of the 1,000 ring-member accounts
5. For each ring-candidate community, `top_account_id` is a member of the dominant ring per `ground_truth.json`
6. In `gold_account_similarity_pairs`, `same_community=true` holds for ≥ 95% of pairs where both accounts are in the same ring per `ground_truth.json`

Writes a JSON artifact to `RESULTS_VOLUME_DIR`. Exits non-zero on any failure.

## Automated Genie testing

`jobs/genie_run.py` runs three analyst-phrased questions against any Genie Space, records the SQL Genie generated and the rows it returned, and writes a JSON artifact to `RESULTS_VOLUME_DIR`. By default it exits 0 as long as Genie responds — no pass/fail gating. Use `GATE=true` to reproduce the legacy CI-gate behavior.

### Questions (same for both spaces)

| Case | Question | After-GDS threshold (observation; gate under `GATE=true`) |
|------|----------|----------------|
| `hub_detection` | "Are there accounts that seem to be the hub of a money movement network that are potentially fraudulent?" | top-20 precision > 0.70 |
| `community_structure` | "Find groups of accounts transferring money heavily among themselves." | max Louvain ring coverage > 0.80 |
| `merchant_overlap` | "Which pairs of accounts have visited the most merchants in common?" | same-ring fraction > 0.60 with ≥5 pairs |

Both the BEFORE (base-table-only) and AFTER (gold-table-enriched) spaces receive the same questions. The demo narrative holds because the gold tables are designed to answer these analyst-phrased questions well; the base tables are not.

### Sample output (`GATE=false`, default)

```
==============================================================================
Genie run — 2026-04-19T04:35:07Z
Space: 01f139ac0f8f1336a622615dcf478f71  Label: after
GATE=false (observation only)
==============================================================================

[1] hub_detection — FRAUD DETECTED
    Question: Are there accounts that seem to be the hub of a money movement
              network that are potentially fraudulent?
    Metric:   precision=1.00  (criterion > 0.70)
    Finding:  20/20 of the top-20 risk-scored accounts are known fraud ring members
              Precision = share of returned hubs that are ground-truth fraud accounts
    Rows:     20
    SQL:      SELECT account_id, risk_score, fraud_risk_tier FROM gold_accounts ORDER BY risk_score DESC LIMIT 20

[2] community_structure — FRAUD RINGS DETECTED
    Question: Find groups of accounts transferring money heavily among
              themselves.
    Metric:   max_ring_coverage=1.00  (criterion > 0.80)
    Finding:  10 community group(s) returned across 10 rows (shape: aggregates_community_map)
              Max ring coverage 100% = the best community covered this share of a real fraud ring
    Rows:     10
    SQL:      SELECT community_id, member_count, top_account_id FROM gold_fraud_ring_communities WHERE is_ring_candidate = true

[3] merchant_overlap — COLLUSION DETECTED
    Question: Which pairs of accounts have visited the most merchants in
              common?
    Metric:   same_ring_fraction=1.00  (criterion > 0.60 with >=5 pairs)
    Finding:  100/100 top-similarity pairs are same-ring; 0 cross-ring; 0 unknown
              Same-ring pairs span 10 distinct fraud ring(s)
              Same-ring fraction = share of returned pairs where both accounts share a ground-truth ring
    Rows:     100
    SQL:      SELECT account_a_id, account_b_id, similarity_score FROM gold_account_similarity_pairs ORDER BY similarity_score DESC LIMIT 100

------------------------------------------------------------------------------
Responded: 3/3
Verdict:   Fraud signal detected in 3/3 tests — Genie surfaced hubs, rings, and collusion.

Artifact: /Volumes/.../genie_test_results/genie_run_after_2026-04-19T04-35-07Z.json
```

BEFORE-space runs show the inverted form — each case reads `NO FRAUD FOUND` / `NO RINGS FOUND` / `NO COLLUSION FOUND`, and the closing `Verdict:` line reports "No fraud signal detected" when the base tables fail to meet the after-GDS criterion.

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

# Run GDS algorithms (writes risk_score, community_id, similarity_score)
uv run validation/run_gds.py

# Verify GDS outputs — prints a pass/fail summary report
uv run validation/verify_gds.py

# Diagnose Node Similarity scores and Jaccard ratios
uv run validation/diagnose_similarity.py
```

All validation scripts read credentials from `automated/.env`.

## Project structure

```
automated/
├── pyproject.toml              # uv project; all dependencies
├── .env.sample                 # config template — copy to .env, never commit .env
├── config.py                   # loads .env, exposes all tuning constants
├── upload_and_create_tables.sh # applies sql/schema.sql, uploads CSVs, loads Delta tables
├── setup_secrets.sh            # stores Neo4j credentials in Databricks secrets
├── genie_instructions.md       # instructions text embedded in Genie Spaces
├── data/                       # generated CSVs + ground_truth.json
├── logs/                       # local mirror of UC Volume artifacts + compare reports
├── setup/                      # one-time local admin scripts (run before a demo)
│   ├── generate_data.py        # generates synthetic fraud dataset to data/
│   └── provision_genie_spaces.py # idempotently configures before/after Genie Spaces
├── diagnostics/                # optional regression checks — not in required sequence
│   └── verify_fraud_patterns.py # checks structural properties of generated data
├── sql/                        # all DDL in one place
│   ├── schema.sql              # base table DDL with UC column comments
│   └── gold_schema.sql         # gold table DDL with UC column comments
├── cli/
│   ├── __init__.py             # Runner instantiation (scripts_dir="jobs")
│   └── __main__.py             # python -m cli entry point
├── jobs/                       # scripts submitted to Databricks via python -m cli submit
│   ├── neo4j_ingest.py         # push Delta tables into Neo4j as a property graph
│   ├── pull_gold_tables.py     # pull GDS features back to Delta gold tables
│   ├── validate_gold_tables.py # data-correctness gate for the three gold tables
│   ├── genie_run.py            # parameterized Genie runner (core logic)
│   ├── genie_run_before.py     # submit wrapper — targets GENIE_SPACE_ID_BEFORE
│   ├── genie_run_after.py      # submit wrapper — AFTER run + optional BEFORE/AFTER comparison
│   ├── compare_report.py       # pure markdown comparison builder, used by genie_run_after.py
│   ├── demo_utils.py           # Genie API + check helpers
│   ├── gold_constants.py       # shared thresholds used by pull and validate
│   └── neo4j_secrets.py        # loads Neo4j credentials from Databricks secret scope
└── validation/                 # local preflight and diagnostic scripts
    ├── validate_neo4j.py       # connection check
    ├── validate_cluster.py     # cluster state and required library check
    ├── validate_neo4j_graph.py # node/edge count and structure checks
    ├── run_gds.py              # runs GDS algorithms against Neo4j Aura
    ├── verify_gds.py           # verifies GDS outputs, prints summary report
    └── diagnose_similarity.py  # Jaccard ratio diagnostics
```
