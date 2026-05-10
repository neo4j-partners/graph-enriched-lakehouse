# Fraud Signal Explorer — analyst-client

A Databricks App for fraud analysts to discover rings in Neo4j, load signals into Delta tables, and analyze them via Genie.

## Quick Start (local, mock backend)

```bash
cd finance-genie/analyst-client
cp env.sample .env
uv sync
uv run python app.py
```

Open http://localhost:8000.

## Quick Start (local, real backend)

Set credentials in `.env`, then run:

```bash
cd finance-genie/analyst-client
cp env.sample .env
# Edit .env and set USE_MOCK_BACKEND=false plus Neo4j/Databricks credentials.
uv sync
uv run python app.py
```

## UI tests

The Playwright suite runs against the deterministic mock backend and does not
require Neo4j or Databricks credentials.

```bash
cd finance-genie/analyst-client
uv sync --group dev
uv run python -m playwright install chromium
uv run pytest tests --browser chromium --tracing retain-on-failure --screenshot only-on-failure
```

When a test fails, inspect the retained trace with:

```bash
uv run python -m playwright show-trace test-results/<trace-file>.zip
```

## Deploy to Databricks Apps

```bash
databricks apps deploy --source-code-path finance-genie/analyst-client
```

Configure `app.yaml` with your resource IDs before deploying.
Databricks Apps uses `uv` when `requirements.txt` is absent and both `pyproject.toml` and `uv.lock` are present.

## Structure

```
analyst-client/
  app.py          # Flask entry point + 4 routes
  backend.py      # MockBackend (dev) and RealBackend (prod)
  app.yaml        # Databricks Apps resource config
  pyproject.toml  # uv project dependencies
  uv.lock
  env.sample      # copy to .env for local config
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
