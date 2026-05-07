# Finance Genie Client

Finance Genie Client is a Streamlit Databricks App that demonstrates the value
of graph enrichment for Databricks Genie in the finance demo.

The app compares two catalogs:

- **Before enrichment:** Genie sees the Silver tables only.
- **After enrichment:** Genie sees the enriched Gold tables with graph-derived
  dimensions such as `risk_score`, `community_id`, `similarity_score`,
  `is_ring_community`, and `fraud_risk_tier`.

The point of the demo is not that the before Genie experience is broken. The
before catalog answers ordinary tabular BI questions. The after catalog expands
the business question surface to include relationship-aware analysis.

## Databricks App Checklist

- Framework selected: Streamlit
- Auth strategy: app auth through Databricks SDK `Config()`
- App resources: SQL warehouse
- Backend data strategy: SQL warehouse over Delta tables
- Deployment method: Databricks Apps CLI or Asset Bundles

## Required Resource

The app requires one SQL warehouse App resource named `sql-warehouse`.
`app.yaml` injects the selected warehouse ID into `DATABRICKS_WAREHOUSE_ID`
with `valueFrom`.

## Environment

Optional environment variables:

- `CATALOG`: defaults to `graph-enriched-lakehouse`
- `SCHEMA`: defaults to `graph-enriched-schema`
- `MCP_SCHEMA_CONNECTION_NAME`: Unity Catalog HTTP connection for an MCP server
  that can return the full schema
- `MCP_SCHEMA_PATH`: MCP JSON-RPC path for the HTTP connection, defaults to `/`
- `MCP_SCHEMA_TOOL_NAME`: MCP tool used by the full schema page, defaults to
  `get_full_schema`
- `MCP_SCHEMA_TOOL_ARGUMENTS`: set to `properties` for Neo4j MCP tools that
  require a `properties` wrapper, `none` for tools that take no arguments, or
  `catalog_schema` to send `catalog` and `schema`

For local development, copy the sample file and fill in your warehouse ID:

```bash
cp .env.local.sample .env.local
```

This file is intentionally much smaller than `finance-genie/automated/.env`.
The app does not need Neo4j credentials, cluster IDs, Genie space IDs, synthetic
data generation settings, or job-runner parameters.

For local data-backed pages, `.env.local` also needs Databricks credentials.
The easiest path is to point the SDK at an existing CLI profile:

```bash
DATABRICKS_CONFIG_PROFILE=<your-databricks-profile>
```

If you are not using `~/.databrickscfg`, set `DATABRICKS_HOST` and a supported
credential such as `DATABRICKS_TOKEN`. The deployed Databricks App does not use
your local `.env.local`; it authenticates with the app service principal and
gets `DATABRICKS_WAREHOUSE_ID` from the `sql-warehouse` resource in `app.yaml`.

## Pages

| Page | Purpose |
| --- | --- |
| Home | Frames the demo as the same Genie experience over an expanded catalog. |
| GDS Enhanced Graph Schema | Shows the graph schema, GDS-added Gold features, and a bounded community sample. |
| Executive Comparison | Shows curated before and after question pairs with SQL evidence. |
| Question Surface | Shows which finance questions become answerable after graph enrichment. |
| Business Value | Quantifies merchant concentration, review workload, book exposure, and transfer flow. |
| Data Lineage | Explains the Silver to Neo4j GDS to Gold to Genie path. |
| MCP Full Schema | Calls a configured MCP server and displays the full live schema response. |

## Data Strategy

The app uses direct SQL evidence from Delta tables rather than live Genie calls.
That keeps the demo repeatable and avoids making the client experience depend on
Genie response latency. Live Genie replay can be added later using the existing
Genie runner artifacts or the Databricks Genie API.

## MCP Schema Page

The MCP Full Schema page uses the Databricks SDK to call an MCP server through a
Unity Catalog HTTP connection. The connection should point at the MCP server base
path and the app service principal needs `USE CONNECTION` on that connection.

The deployed app defaults to the Neo4j MCP demo connection
`neo4j_agentcore_mcp` and tool `neo4j-mcp-server-target___get-schema`. That
tool is called with `MCP_SCHEMA_TOOL_ARGUMENTS=properties`, which sends the
required `properties` wrapper argument. For other MCP schema servers, override
`MCP_SCHEMA_TOOL_NAME` and set `MCP_SCHEMA_TOOL_ARGUMENTS=catalog_schema` when
the tool expects the configured `catalog` and `schema` arguments, or `none` when
the tool expects no arguments. The page preserves the raw MCP response and also
normalizes common schema response shapes into tables, columns, and relationships.

## Local Development

From this directory:

```bash
./scripts/start_local.sh
```

For live SQL queries, also set:

```bash
export DATABRICKS_WAREHOUSE_ID=<warehouse-id>
export DATABRICKS_CONFIG_PROFILE=<your-databricks-profile>
export CATALOG=graph-enriched-lakehouse
export SCHEMA=graph-enriched-schema
export MCP_SCHEMA_CONNECTION_NAME=neo4j_agentcore_mcp
export MCP_SCHEMA_TOOL_NAME=neo4j-mcp-server-target___get-schema
export MCP_SCHEMA_TOOL_ARGUMENTS=properties
```

You can place those values in `.env.local`; `scripts/start_local.sh` and
`scripts/test_local.sh` load it automatically.

To run a local smoke test:

```bash
./scripts/test_local.sh
```

The test compiles all app modules, starts Streamlit on port `18501`, checks that
the home page returns HTTP 200, then stops the test server.

To stop an interactive local server started on the default port:

```bash
./scripts/stop_local.sh
```

Use `PORT=<port> ./scripts/stop_local.sh` if you started it on a different port.

## Deploy

Create and deploy with the deployment wrapper:

```bash
./scripts/deploy_app.sh
```

Optional environment variables:

- `APP_NAME`: defaults to `finance-genie-client`
- `WORKSPACE_SOURCE_PATH`: defaults to `/Workspace/Users/<current-user>/apps/<app-name>`
- `DATABRICKS_CONFIG_PROFILE`: passed to the Databricks CLI as `--profile`
- `DATABRICKS_WAREHOUSE_ID`: binds the app resource key `sql-warehouse`
- `GRANT_APP_SP_SCHEMA_ACCESS`: set to `true` to grant the app service principal `USE_CATALOG`, `USE_SCHEMA`, and `SELECT` for `CATALOG.SCHEMA`
- `MCP_SCHEMA_CONNECTION_NAME`: defaults to `neo4j_agentcore_mcp`
- `GRANT_APP_SP_MCP_CONNECTION_ACCESS`: defaults to `true` and grants the app service principal `USE CONNECTION` on `MCP_SCHEMA_CONNECTION_NAME`

The script loads `.env.local` when present. It creates the app if needed, binds
the SQL warehouse resource when `DATABRICKS_WAREHOUSE_ID` is set, grants MCP
connection access by default, uploads source to the workspace, deploys from that
workspace path, and prints the app details.

The app reads that resource through `DATABRICKS_WAREHOUSE_ID` `valueFrom` in
`app.yaml`.

## Files

```text
finance-client/
├── app.py
├── app.yaml
├── backend.py
├── pages/
│   ├── 1_GDS_Enhanced_Graph_Schema.py
│   ├── 2_Executive_Comparison.py
│   ├── 3_Question_Surface.py
│   ├── 4_Business_Value.py
│   ├── 5_Data_Lineage.py
│   └── 6_MCP_Full_Schema.py
├── scripts/
│   ├── deploy_app.sh
│   ├── start_local.sh
│   ├── stop_local.sh
│   └── test_local.sh
├── requirements.txt
└── README.md
```
