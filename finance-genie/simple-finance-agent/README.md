# Simple Finance Agent

This directory contains one deployable Databricks Model Serving agent. The
agent calls the Neo4j MCP server already configured by
`finance-genie/neo4j-mcp-demo`.

This is intentionally not a multi-agent project. There is no Supervisor Agent,
Genie Space, local server, or MCP provisioning here. The only job of this
project is to deploy one `ResponsesAgent` endpoint that discovers tools from an
existing Unity Catalog external MCP connection and uses those tools to run
read-only Neo4j Cypher.

Use this endpoint as the simple finance agent in a Databricks Supervisor Agent
setup. Connect the BEFORE Genie Space separately in Databricks, then route
business-table questions to Genie and graph-evidence questions to this endpoint.

## Why this name

`simple-finance-agent` is the clearest name for this folder because it describes
the deployed artifact instead of the optional orchestration around it:

- `simple-finance-agent/` deploys one agent endpoint.
- `neo4j-mcp-demo/` creates and validates the external MCP connection.
- Databricks Supervisor Agent and Genie Space setup happen manually in
  Databricks.

The previous name implied this folder created the Supervisor Agent system. It
does not.

## Databricks model

This project follows the Databricks Model Serving agent deployment path:

- The agent is implemented with MLflow `ResponsesAgent`, which Databricks
  documents as the recommended compatibility interface for AI Playground,
  evaluation, monitoring, and tracing.
- The Neo4j tool server is reached through the Databricks external MCP proxy at
  `/api/2.0/mcp/external/{connection_name}`.
- The deploy job logs the agent with the LLM serving endpoint and MCP resources,
  registers it in Unity Catalog, then deploys it with `databricks.agents.deploy`.

Databricks now recommends Databricks Apps for new custom agent applications.
This project stays on Model Serving because the goal is a small deployable
endpoint that can be attached to a manually configured Supervisor Agent.

## Prerequisite

Create and validate the Neo4j MCP Unity Catalog connection first:

```bash
cd ../neo4j-mcp-demo
./deploy.sh --profile <your-databricks-profile> --compute serverless
```

The connection name from that setup must match `UC_CONNECTION_NAME` here. The
default is `neo4j_agentcore_mcp`.

The Databricks identity that deploys and serves this endpoint needs access to:

- The LLM serving endpoint named by `LLM_ENDPOINT_NAME`.
- The Unity Catalog external MCP connection named by `UC_CONNECTION_NAME`.
- The Unity Catalog catalog and schema where `UC_MODEL_NAME` is registered.

## Setup

From this directory:

```bash
cd ..
cp .env.sample .env
cd simple-finance-agent
```

Set the Databricks profile, workspace path, Unity Catalog model location, LLM
endpoint, serving endpoint name, and `UC_CONNECTION_NAME`.

Required values:

- `DATABRICKS_PROFILE`, unless standard Databricks SDK auth is already set
- `SIMPLE_FINANCE_AGENT_DATABRICKS_WORKSPACE_DIR`, or `DATABRICKS_WORKSPACE_DIR`
- `CATALOG`
- `SCHEMA`
- `UC_CONNECTION_NAME`
- `LLM_ENDPOINT_NAME`
- `SIMPLE_FINANCE_AGENT_UC_MODEL_NAME`, or `UC_MODEL_NAME`
- `SIMPLE_FINANCE_AGENT_MODEL_SERVING_ENDPOINT_NAME`, or `MODEL_SERVING_ENDPOINT_NAME`

Recommended root `.env` values:

```bash
SIMPLE_FINANCE_AGENT_DATABRICKS_WORKSPACE_DIR=/Users/<you>@<domain>/graph-enriched-lakehouse/simple-finance-agent
SIMPLE_FINANCE_AGENT_UC_MODEL_NAME=simple-finance-agent
SIMPLE_FINANCE_AGENT_MODEL_SERVING_ENDPOINT_NAME=simple-finance-agent
```

The `SIMPLE_FINANCE_AGENT_*` names let the shared root `.env` keep the
`neo4j-mcp-demo` model and endpoint defaults without accidentally deploying
this agent under those names.

## Deploy

Run a local syntax check:

```bash
./scripts/test_local.sh
```

Start or update the remote serving endpoint:

```bash
./scripts/start_remote.sh --profile <your-databricks-profile> --compute serverless
```

Or run the full local check, deploy, readiness wait, and smoke test:

```bash
./scripts/deploy_all.sh --profile <your-databricks-profile> --compute serverless
```

## Test

Validate and query the endpoint:

```bash
./scripts/test_remote.sh --profile <your-databricks-profile>
```

Send a custom prompt:

```bash
./scripts/test_remote.sh --profile <your-databricks-profile> --prompt "Use Neo4j MCP to show the graph schema."
```

## Stop

Delete the serving endpoint to stop remote serving costs:

```bash
./scripts/stop_remote.sh --profile <your-databricks-profile> --yes
```

This deletes only the serving endpoint named by `MODEL_SERVING_ENDPOINT_NAME`.
It does not delete the Neo4j MCP gateway, UC connection, registered model, or
any objects managed by `finance-genie/neo4j-mcp-demo`.

## Manual Supervisor setup

After deployment, create the multi-agent experience in Databricks:

1. Add this Model Serving endpoint as the simple finance graph agent.
2. Add the BEFORE Genie Space as the structured-data agent.
3. Configure Supervisor instructions to call this agent for graph schema,
   relationship, neighborhood, and read-only Cypher questions.
4. Configure Supervisor instructions to call Genie for account, merchant,
   transaction, balance, and other Silver-table business questions.

Keeping this setup manual avoids duplicating Databricks UI configuration in
this repo and keeps this folder focused on the part that needs code: deploying
the MCP-backed agent endpoint.

## References

Databricks documentation used for this project shape:

- [Create an AI agent](https://docs.databricks.com/aws/en/generative-ai/agent-framework/create-agent):
  explains the supported Databricks agent authoring paths, including custom
  Python agents and the `ResponsesAgent` compatibility surface.
- [Install an external MCP server](https://docs.databricks.com/aws/en/generative-ai/mcp/external-mcp):
  covers external MCP server setup through Unity Catalog HTTP connections,
  required privileges, the managed proxy URL, and `USE CONNECTION` sharing.
- [Connect agents to external services](https://docs.databricks.com/aws/en/generative-ai/agent-framework/external-connection-tools):
  describes the external MCP approach and the `/api/2.0/mcp/external/{connection_name}`
  URL used by this agent.
- [Deploy an agent for generative AI applications on Model Serving](https://docs.databricks.com/aws/en/generative-ai/agent-framework/deploy-agent):
  documents `databricks.agents.deploy`, Unity Catalog model registration
  requirements, endpoint updates, and Model Serving deployment behavior.
- [Connect agents to structured data](https://docs.databricks.com/aws/en/generative-ai/agent-framework/structured-retrieval-tools):
  documents the Databricks-side Genie integration patterns and why this repo
  keeps Genie/Supervisor wiring separate from this MCP-backed endpoint.
- [Use Supervisor Agent to create a coordinated multi-agent system](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor):
  documents the UI-first Supervisor Agent setup that can connect this endpoint
  with the BEFORE Genie Space.
