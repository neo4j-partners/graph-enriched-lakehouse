# Simple Finance Analyst

A Databricks App for finance analysts to discover rings in Neo4j, load signals into Delta tables, and analyze them via Genie.

## Quick Start (local, mock backend)

```bash
cd finance-genie
cp .env.sample .env
# Edit .env. Leave USE_MOCK_BACKEND=true for mock local runs.
cd simple-finance-analyst
uv sync
uv run python app.py
```

Open http://localhost:8000.

## Quick Start (local, real backend)

Set credentials in `.env`, then run:

```bash
cd finance-genie
cp .env.sample .env
# Edit .env and set USE_MOCK_BACKEND=false plus Neo4j/Databricks credentials.
cd simple-finance-analyst
uv sync
uv run python app.py
```

## UI tests

The test suite includes Flask route contract tests, backend query contract tests,
and Playwright UI flow tests. It runs against the deterministic mock backend and
does not require Neo4j or Databricks credentials.

```bash
cd finance-genie/simple-finance-analyst
uv sync --group dev
uv run python -m playwright install chromium
uv run pytest
```

When a test fails, inspect the retained trace with:

```bash
uv run python -m playwright show-trace test-results/<trace-file>.zip
```

## Deploy to Databricks Apps

The app is a Flask service deployed with Gunicorn. Runtime binding is configured
in `gunicorn_config.py`, which reads `DATABRICKS_APP_PORT`.

Use the deployment wrapper from the `simple-finance-analyst` directory:

```bash
cd finance-genie/simple-finance-analyst
./scripts/deploy_app.sh
```

For live remote deployments, prefer the bundle so app resources are attached
with the same keys referenced by `app.yaml`:

```bash
cd finance-genie/simple-finance-analyst
databricks bundle deploy \
  --profile "$DATABRICKS_PROFILE" \
  --var "warehouse_id=$DATABRICKS_WAREHOUSE_ID" \
  --var "genie_space_id=$GENIE_SPACE_ID" \
  --var "neo4j_secret_scope=${SIMPLE_FINANCE_ANALYST_SECRET_SCOPE:-simple-finance-analyst}"
databricks bundle run simple-finance-analyst-app --profile "$DATABRICKS_PROFILE"
```

Optional environment variables:

| Env var | Default | Effect |
|---|---|---|
| `APP_NAME` | `simple-finance-analyst` | Databricks App name passed as the required positional `APP_NAME` |
| `WORKSPACE_SOURCE_PATH` | `/Workspace/Users/<current-user>/apps/<app-name>` | Workspace Files path uploaded before deployment |
| `DATABRICKS_CONFIG_PROFILE` | unset | Passed to the Databricks CLI as `--profile` |

The Databricks CLI direct deploy form requires both an app name and a workspace
source path. A local path such as `simple-finance-analyst` is rejected by the API:

```bash
databricks apps deploy simple-finance-analyst \
  --source-code-path /Workspace/Users/<user>/apps/simple-finance-analyst
```

Configure the app resources in Databricks Apps so `app.yaml` can resolve
the live backend resources:

| Resource key | Type | Used for |
|---|---|---|
| `sql-warehouse` | SQL warehouse | `DATABRICKS_WAREHOUSE_ID` |
| `genie-space` | Genie space | `GENIE_SPACE_ID` |
| `neo4j-uri` | Secret | `NEO4J_URI` |
| `neo4j-username` | Secret | `NEO4J_USERNAME` |
| `neo4j-password` | Secret | `NEO4J_PASSWORD` |

Databricks Apps uses `uv` when `requirements.txt` is absent and both `pyproject.toml` and `uv.lock` are present.

## Structure

```
simple-finance-analyst/
  app.py          # Flask entry point + 4 routes
  backend.py      # MockBackend (dev) and RealBackend (prod)
  gunicorn_config.py  # Gunicorn bind/workers/timeout for Databricks Apps
  app.yaml        # Databricks Apps resource config
  pyproject.toml  # uv project dependencies
  uv.lock
  env.sample      # compatibility-only; prefer ../.env.sample
  scripts/
    deploy_app.sh # uploads clean source to Workspace Files, then deploys
  static/
    index.html    # Three-screen wizard
    app.js        # Fetch wiring + Cytoscape graph rendering
    style.css
```

## Switching backends

| Env var | Value | Effect |
|---|---|---|
| `USE_MOCK_BACKEND` | `true` (default) | Uses seeded mock data, no external connections |
| `USE_MOCK_BACKEND` | `false` | Connects to Neo4j and Databricks |
| `SIMPLE_FINANCE_ANALYST_CATALOG` | `graph-enriched-lakehouse` | Catalog containing enriched gold tables |
| `SIMPLE_FINANCE_ANALYST_SCHEMA` | `graph-enriched-schema` | Schema containing enriched gold tables |

`app.yaml` sets `USE_MOCK_BACKEND=false` for deployed live-backend use. Local
mock runs can still set `USE_MOCK_BACKEND=true` in `finance-genie/.env`.
