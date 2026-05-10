# simple-finance-agnet

This directory contains a minimal Databricks Model Serving agent that calls the
Neo4j MCP server already configured by `finance-genie/neo4j-mcp-demo`.

There is no Supervisor Agent, Genie Space, local server, or MCP provisioning in
this demo. It only deploys one `ResponsesAgent` endpoint that discovers tools
from the existing Unity Catalog MCP connection and uses those tools to run
read-only Neo4j Cypher.

## Prerequisite

Create and validate the Neo4j MCP Unity Catalog connection first:

```bash
cd ../neo4j-mcp-demo
./deploy.sh --profile azure-rk-knight --compute serverless
```

The connection name from that setup must match `UC_CONNECTION_NAME` here. The
default is `neo4j_agentcore_mcp`.

## Setup

From this directory:

```bash
cd ..
cp .env.sample .env
cd multi-agent-demo
```

Set the Databricks profile, workspace path, Unity Catalog model location, LLM
endpoint, serving endpoint name, and `UC_CONNECTION_NAME`.

Required values:

- `DATABRICKS_PROFILE`, unless standard Databricks SDK auth is already set
- `DATABRICKS_WORKSPACE_DIR`
- `CATALOG`
- `SCHEMA`
- `UC_CONNECTION_NAME`
- `LLM_ENDPOINT_NAME`
- `UC_MODEL_NAME`
- `MODEL_SERVING_ENDPOINT_NAME`

## Deploy

Run a local syntax check:

```bash
./scripts/test_local.sh
```

Start or update the remote serving endpoint:

```bash
./scripts/start_remote.sh --profile azure-rk-knight --compute serverless
```

Or run the full local check, deploy, readiness wait, and smoke test:

```bash
./scripts/deploy_all.sh --profile azure-rk-knight --compute serverless
```

## Test

Validate and query the endpoint:

```bash
./scripts/test_remote.sh --profile azure-rk-knight
```

Send a custom prompt:

```bash
./scripts/test_remote.sh --profile azure-rk-knight --prompt "Use Neo4j MCP to show the graph schema."
```

## Stop

Delete the serving endpoint to stop remote serving costs:

```bash
./scripts/stop_remote.sh --profile azure-rk-knight --yes
```

This deletes only the serving endpoint named by `MODEL_SERVING_ENDPOINT_NAME`.
It does not delete the Neo4j MCP gateway, UC connection, registered model, or
any objects managed by `finance-genie/neo4j-mcp-demo`.
