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
    "dbxcarta>=0.2.35",
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

Fill in Databricks, SQL warehouse, chat endpoint, and Neo4j values in `.env`.

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

## Local Demo

The local demo loads `.env` from this `sql-semantics/` directory.

```bash
uv run python -m sql_semantics.local_demo preflight
uv run python -m sql_semantics.local_demo questions
uv run python -m sql_semantics.local_demo ask --question-id fg_q01 --show-context
uv run python -m sql_semantics.local_demo sql "SELECT COUNT(*) FROM \`graph-enriched-lakehouse\`.\`graph-enriched-schema\`.accounts"
```

The local demo accepts only `SELECT`, `WITH`, and `EXPLAIN` statements.

## Tests

Run non-live tests:

```bash
uv run pytest
```

These tests validate the preset protocol, env overlay, readiness formatting,
question lookup, context printing, and read-only SQL guardrails.

## Preset Defaults

The preset targets the full `graph-enriched-schema`, enables table, column,
value, schema, and database embeddings, and enables semantic relationship
inference. Criteria injection is disabled because the Finance Genie inferred
relationships do not carry literal join-predicate strings.

For a cheaper first validation run, override embedding flags in `.env` and
start with `DBXCARTA_INCLUDE_EMBEDDINGS_TABLES=true` only.
