# Fraud Signal Explorer — analyst-client

A Databricks App for fraud analysts to discover rings in Neo4j, load signals into Delta tables, and analyze them via Genie.

## Quick Start (local, mock backend)

```bash
cd finance-genie/analyst-client
uv venv && uv pip install flask
USE_MOCK_BACKEND=true uv run python app.py
```

Open http://localhost:8000.

## Quick Start (local, real backend)

Set credentials before running:

```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your-password
export DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...
export GENIE_SPACE_ID=<space-id>
export DATABRICKS_WAREHOUSE_ID=<warehouse-id>

cd finance-genie/analyst-client
USE_MOCK_BACKEND=false uv run python app.py
```

## Deploy to Databricks Apps

```bash
databricks apps deploy --source-code-path finance-genie/analyst-client
```

Configure `app.yaml` with your resource IDs before deploying.

## Structure

```
analyst-client/
  app.py          # Flask entry point + 4 routes
  backend.py      # MockBackend (dev) and RealBackend (prod)
  app.yaml        # Databricks Apps resource config
  requirements.txt
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
