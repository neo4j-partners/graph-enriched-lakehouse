# Fraud Signal Explorer — analyst-client

A Databricks App for fraud analysts to discover rings in Neo4j, load signals into Delta tables, and analyze them via Genie.

## Quick Start (local, mock backend)

```bash
cd finance-genie
cp .env.sample .env
# Edit .env. Leave USE_MOCK_BACKEND=true for mock local runs.
cd analyst-client
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
cd analyst-client
uv sync
uv run python app.py
```

## UI tests

The test suite includes Flask route contract tests, backend query contract tests,
and Playwright UI flow tests. It runs against the deterministic mock backend and
does not require Neo4j or Databricks credentials.

```bash
cd finance-genie/analyst-client
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

Use the deployment wrapper from the `analyst-client` directory:

```bash
cd finance-genie/analyst-client
./scripts/deploy_app.sh
```

Optional environment variables:

| Env var | Default | Effect |
|---|---|---|
| `APP_NAME` | `finance-genie-analyst-client` | Databricks App name passed as the required positional `APP_NAME` |
| `WORKSPACE_SOURCE_PATH` | `/Workspace/Users/<current-user>/apps/<app-name>` | Workspace Files path uploaded before deployment |
| `DATABRICKS_CONFIG_PROFILE` | unset | Passed to the Databricks CLI as `--profile` |

The Databricks CLI direct deploy form requires both an app name and a workspace
source path. A local path such as `analyst-client` is rejected by the API:

```bash
databricks apps deploy finance-genie-analyst-client \
  --source-code-path /Workspace/Users/<user>/apps/finance-genie-analyst-client
```

Configure the app resources in Databricks Apps so `app.yaml` can resolve
`DATABRICKS_WAREHOUSE_ID` from the `sql-warehouse` resource. Real-backend
deployments also need `GENIE_SPACE_ID`, either from a `genie-space` app resource
or environment configuration.

Databricks Apps uses `uv` when `requirements.txt` is absent and both `pyproject.toml` and `uv.lock` are present.

## Structure

```
analyst-client/
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

`app.yaml` currently sets `USE_MOCK_BACKEND=true` for demo-safe deployment. For
real backend use, set it to `false`, configure the SQL warehouse and Genie
resources, and provide `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD` from
Databricks secret resources or environment configuration.
