# SQL Semantics

`sql-semantics` is a standalone Python package that tests using dbxcarta from
outside the dbxcarta repository. It owns a Finance Genie dbxcarta preset and
points at Finance Genie Unity Catalog tables that have already been created by
the upstream data pipeline.

The package exposes this dbxcarta preset:

```text
sql_semantics:preset
```

## Layout

```text
sql-semantics/
├── pyproject.toml
├── databricks.yml
├── README.md
├── .env.sample
├── src/sql_semantics/
│   ├── __init__.py
│   ├── finance_genie.py
│   ├── local_demo.py
│   ├── upload_questions.py
│   └── questions.json
└── tests/
    ├── test_preset.py
    └── test_local_demo.py
```

## Boundary

Finance Genie owns synthetic data generation, the Unity Catalog tables, the GDS
enrichment pipeline, Gold tables, and Genie demo assets.

This package owns only the dbxcarta-facing configuration:

- Finance Genie table contract
- dbxcarta environment overlay
- table readiness check
- bundled question fixture upload
- optional local read-only CLI demo

It does not import modules from this repository's root-level `finance-genie/`
tree and does not depend on being inside the dbxcarta repository.

## Dependency Model

`pyproject.toml` declares dbxcarta as a normal dependency:

```toml
dependencies = [
    "dbxcarta>=0.2.38",
    "databricks-sdk>=0.40",
    "python-dotenv",
]
```

For local development in this workspace, `uv` resolves dbxcarta to the sibling
checkout:

```toml
[tool.uv.sources]
dbxcarta = { path = "/Users/ryanknight/projects/databricks/dbxcarta", editable = true }
```

That path is intentionally absolute so this package behaves like an external
consumer rather than a nested dbxcarta example.

## Prerequisites

Before running live dbxcarta workflows, create the Finance Genie data in Unity
Catalog by running the upstream Finance Genie setup path from this repository's
`finance-genie/enrichment-pipeline` project.

Default Unity Catalog scope:

```text
graph-enriched-lakehouse.graph-enriched-schema
```

Required base tables:

- `accounts`
- `merchants`
- `transactions`
- `account_links`
- `account_labels`

Optional Gold tables:

- `gold_accounts`
- `gold_account_similarity_pairs`
- `gold_fraud_ring_communities`

Gold tables are optional for the default readiness check. Use dbxcarta's strict
optional flag when you want readiness to require them.

## Setup

Run commands from this directory:

```bash
cd /Users/ryanknight/projects/databricks/graph-on-databricks/sql-semantics
uv sync
```

Copy the local environment sample if you want to run the local demo:

```bash
cp .env.sample .env
```

Fill in the following values in `.env` before any live commands:

| Variable | Description |
|---|---|
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse ID for query execution |
| `DATABRICKS_CLUSTER_ID` | Cluster ID for submit-entrypoint jobs |
| `DBXCARTA_CHAT_ENDPOINT` | Model serving endpoint for SQL generation |
| `NEO4J_URI` | Neo4j connection URI |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |

All other values in `.env.sample` reflect the Finance Genie preset defaults and
do not need to change unless you are targeting a different catalog or schema.

## Preset Commands

Print the dbxcarta environment overlay:

```bash
uv run dbxcarta preset sql_semantics:preset --print-env
```

Check table readiness:

```bash
uv run dbxcarta preset sql_semantics:preset --check-ready
```

Require optional Gold tables during readiness:

```bash
uv run dbxcarta preset sql_semantics:preset --check-ready --strict-optional
```

Upload bundled questions to the UC Volume path named by
`DBXCARTA_CLIENT_QUESTIONS`:

```bash
uv run dbxcarta preset sql_semantics:preset --upload-questions
```

## Semantic Layer Build

After readiness passes and dbxcarta secrets are configured, build and verify the
semantic layer:

```bash
uv run dbxcarta upload --wheel
uv run dbxcarta upload --all
uv run dbxcarta submit-entrypoint ingest
uv run dbxcarta verify
```

Run the dbxcarta client evaluation:

```bash
uv run dbxcarta submit-entrypoint client
```

## Databricks Jobs

`databricks.yml` defines two jobs as a Databricks Asset Bundle. These are the
recommended deployment path for consumers who do not want to run
`submit-entrypoint` from a local CLI.

### Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `warehouse_id` | Yes | none | SQL warehouse ID for client evaluation runs |
| `catalog` | No | `graph-enriched-lakehouse` | UC catalog |
| `schema` | No | `graph-enriched-schema` | UC schema |
| `volume` | No | `graph-enriched-volume` | UC volume for run artifacts |
| `secret_scope` | No | `dbxcarta-neo4j` | Databricks secret scope holding Neo4j credentials |
| `chat_endpoint` | No | `databricks-claude-sonnet-4-6` | Model serving endpoint for SQL generation |

The `warehouse_id` variable has no default and must be supplied at deploy time.

The Neo4j secret scope must contain three keys: `neo4j_uri`, `neo4j_username`,
and `neo4j_password`. Create them with the Databricks CLI:

```bash
databricks secrets put-secret dbxcarta-neo4j neo4j_uri --string-value bolt://...
databricks secrets put-secret dbxcarta-neo4j neo4j_username --string-value neo4j
databricks secrets put-secret dbxcarta-neo4j neo4j_password --string-value ...
```

### Deploy and run

Validate the bundle configuration:

```bash
databricks bundle validate
```

Deploy to the `dev` target:

```bash
databricks bundle deploy -t dev --var="warehouse_id=<your-warehouse-id>"
```

Deploy to `prod`:

```bash
databricks bundle deploy -t prod --var="warehouse_id=<your-warehouse-id>"
```

Before deploying to `prod`, update the `run_as.service_principal_name` field in
`databricks.yml` to match the service principal that should own the jobs.

Run the ingest job:

```bash
databricks bundle run sql_semantics_ingest
```

Run the client evaluation job:

```bash
databricks bundle run sql_semantics_client
```

### Override variables

Pass multiple overrides at deploy time:

```bash
databricks bundle deploy -t prod \
  --var="warehouse_id=abc123" \
  --var="catalog=my-catalog" \
  --var="schema=my-schema"
```

Or set them as environment variables:

```bash
export BUNDLE_VAR_warehouse_id=abc123
databricks bundle deploy -t prod
```

## Local Demo

The local demo loads `.env` from this `sql-semantics/` directory.

```bash
uv run python -m sql_semantics.local_demo preflight
uv run python -m sql_semantics.local_demo questions
uv run python -m sql_semantics.local_demo ask --question-id fg_q01 --show-context
uv run python -m sql_semantics.local_demo sql "SELECT COUNT(*) FROM \`graph-enriched-lakehouse\`.\`graph-enriched-schema\`.accounts"
```

The local demo accepts only `SELECT`, `WITH`, and `EXPLAIN` statements.

Additional flags for `ask`:

| Flag | Description |
|---|---|
| `--show-context` | Print the retrieved graph context node IDs |
| `--show-prompt` | Print the full prompt sent to the model |
| `--no-compare-reference` | Skip result comparison with `reference_sql` |
| `--limit N` | Limit printed rows (default: 20) |

## Tests

### Non-live tests

Run from this directory:

```bash
uv run pytest
```

`pytest` defaults to skipping tests marked `live`. The non-live suite covers:

**`test_preset.py`**
- `FinanceGeniePreset` satisfies the `Preset` protocol and optional `ReadinessCheckable` and `QuestionsUploadable` capabilities
- `sql_semantics:preset` resolves correctly via `load_preset`
- `preset.env()` validates against `Settings` without errors
- Preset rejects invalid catalog identifiers
- `ReadinessReport` correctly classifies present, missing required, and missing optional tables
- `report.ok()` is lenient on optional tables; `report.ok(strict_optional=True)` requires them

**`test_local_demo.py`**
- `_ensure_read_only_sql` accepts `SELECT`, `WITH`, and `EXPLAIN`
- `_ensure_read_only_sql` rejects mutations and compound statements
- `_resolve_question` returns an ad-hoc `Question` for free-form text
- `_resolve_question` looks up a question by ID from a JSON file
- The `questions` command lists questions to stdout
- `_print_rows` handles zero-limit and missing column names
- `_print_context` prints node IDs and the expanded context text

### Live tests

Live tests require a configured `.env`, a running Neo4j instance with an
ingested graph, and a reachable Databricks workspace. Run them explicitly:

```bash
uv run pytest -m live
```

### Run a single test file

```bash
uv run pytest tests/test_preset.py
uv run pytest tests/test_local_demo.py
```

### Run a specific test

```bash
uv run pytest tests/test_preset.py::test_env_overlay_validates_against_settings
```

## Preset Defaults

The preset targets the full `graph-enriched-schema`, enables table, column,
value, schema, and database embeddings, and enables semantic relationship
inference. Criteria injection is disabled because the Finance Genie inferred
relationships do not carry literal join-predicate strings.

For a cheaper first validation run, override embedding flags in `.env` and
start with `DBXCARTA_INCLUDE_EMBEDDINGS_TABLES=true` only.
