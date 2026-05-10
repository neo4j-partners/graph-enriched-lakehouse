# Neo4j MCP Demo

CLI-driven setup for a Neo4j MCP server exposed to Databricks through an AWS AgentCore gateway, a Unity Catalog HTTP connection, and a Databricks Model Serving agent endpoint.

## What This Builds

- A Databricks secret scope containing AgentCore OAuth machine-to-machine credentials.
- A Unity Catalog HTTP connection with MCP enabled.
- A Unity Catalog catalog and schema for the registered agent model.
- A LangGraph `ResponsesAgent` that discovers Neo4j MCP tools through the Databricks MCP proxy.
- A Model Serving endpoint deployed with `databricks.agents.deploy`.

## Prerequisites

- `uv` installed locally.
- Databricks CLI or SDK authentication configured through a profile, `DATABRICKS_HOST` plus `DATABRICKS_TOKEN`, or standard Databricks SDK auth.
- Unity Catalog enabled in the target workspace.
- Managed MCP Servers preview enabled in the target workspace.
- `CREATE CONNECTION` privilege on the Unity Catalog metastore.
- Permission to create or use the configured secret scope, catalog, schema, model, and serving endpoint.
- A Pro or Serverless SQL warehouse, or a DBR 15.4 LTS or later cluster using Standard or Dedicated access mode.
- A Neo4j MCP server that supports Streamable HTTP transport.
- `.mcp-credentials.json` copied into this directory by the operator.

## Quick Start

From this directory:

```bash
cd finance-genie/neo4j-mcp-demo
cd ..
cp .env.sample .env
cd neo4j-mcp-demo
```

Copy the AgentCore-generated credentials file into this directory:

```bash
cp /path/to/.mcp-credentials.json .mcp-credentials.json
```

Edit `.env` and set at least:

- `DATABRICKS_PROFILE` or standard Databricks SDK auth environment variables
- `DATABRICKS_WAREHOUSE_ID` or `DATABRICKS_CLUSTER_ID`
- `DATABRICKS_WORKSPACE_DIR`
- `MCP_SECRET_SCOPE`
- `UC_CONNECTION_NAME`
- `CATALOG`
- `SCHEMA`
- `LLM_ENDPOINT_NAME`, for example `databricks-claude-sonnet-4-6` if available in your region
- `MODEL_SERVING_ENDPOINT_NAME`

Validate the local credential file:

```bash
uv run validation/validate_credentials.py
```

Deploy everything and run the endpoint smoke test:

```bash
./deploy.sh
```

The deploy script runs the setup, Databricks-side validation jobs, agent
deployment, endpoint readiness polling, and smoke test in order. It stops at
the first failed step.

If an existing connection has different settings, recreate it explicitly:

```bash
./deploy.sh --replace-connection
```

To choose Databricks job compute for the submitted validation and deploy jobs:

```bash
./deploy.sh --compute serverless
```

The equivalent step-by-step sequence is:

```bash
./setup_secrets.sh
uv run setup/provision_connection.py
uv run validation/validate_connection.py
uv run setup/provision_uc_resources.py
```

If an existing connection has different settings during the manual flow,
recreate it explicitly:

```bash
uv run setup/provision_connection.py --replace
```

Upload job code and run the Databricks-side sequence:

```bash
uv run python -m cli upload --all
uv run python -m cli submit 00_validate_mcp_gateway.py
uv run python -m cli submit 01_deploy_agent.py
uv run validation/validate_endpoint.py
uv run python -m cli submit 02_validate_endpoint.py
```

## MCP Validation

Use these checks when you want to isolate where MCP connectivity is failing.
Run commands from `finance-genie/neo4j-mcp-demo`. The validation clients load
Databricks auth and object names from `.env`, including `DATABRICKS_PROFILE`
when you use profile-based auth.

Validate the local AgentCore credential file without calling Databricks or the
MCP gateway:

```bash
uv run validation/validate_credentials.py
```

Test the AgentCore MCP gateway directly from your laptop. This performs the
OAuth client credentials flow, sends a JSON-RPC `tools/list` request to the
gateway, and prints the discovered tool names without printing secret values:

```bash
uv run validation/validate_mcp_gateway_local.py
```

Expected direct gateway tools include:

- `neo4j-mcp-server-target___get-schema`
- `neo4j-mcp-server-target___read-cypher`
- `neo4j-mcp-server-target___list-gds-procedures`

Validate the Databricks Unity Catalog HTTP connection and MCP flag from your
local machine:

```bash
uv run validation/validate_connection.py
```

Run the Databricks-side MCP validation job. This verifies that Databricks can
read the stored OAuth secrets, reach the AgentCore gateway, list direct gateway
tools, and list tools through the UC MCP proxy:

```bash
uv run python -m cli submit --compute serverless 00_validate_mcp_gateway.py
```

After the agent is deployed, validate serving endpoint readiness and then run a
tool-backed smoke test:

```bash
uv run validation/validate_endpoint.py
uv run python -m cli submit --compute serverless 02_validate_endpoint.py
```

## Notes

- `.mcp-credentials.json` and `.env` are local operator inputs and must not be committed.
- The MCP flag is set with the preview HTTP connection option `is_mcp_connection 'true'`. The setup validates the resulting metadata and the Databricks MCP proxy instead of relying only on SQL success.
- External MCP and HTTP connections are Public Preview Databricks features. Re-test the provisioning step when upgrading Databricks SDK packages or moving to a new workspace.
- The deploy job logs MCP resource dependencies with `DatabricksMCPClient.get_databricks_resources()` so Model Serving can authenticate to the Unity Catalog connection.
- The default LLM endpoint avoids `databricks-claude-3-7-sonnet`, which Databricks documentation marks as retired on April 12, 2026. Confirm `databricks-claude-sonnet-4-6` is available in your region or choose another current chat endpoint.
- Databricks currently recommends Databricks Apps for new agents that need full server control. This demo keeps Model Serving to match the original notebook flow.

## Troubleshooting

- `validate_credentials.py` fails: confirm the local `.mcp-credentials.json` contains `gateway_url`, `client_id`, `client_secret`, `token_url`, and `scope`.
- `provision_connection.py` fails with drift: rerun with `--replace` after confirming the existing connection can be recreated.
- `00_validate_mcp_gateway.py` fails: check AgentCore gateway reachability, OAuth credentials, and whether the Databricks workspace can reach the gateway host.
- `validate_endpoint.py` fails: wait for the serving endpoint deployment to finish, then rerun validation.

## References

- Databricks external MCP servers: https://docs.databricks.com/aws/en/generative-ai/mcp/external-mcp
- Databricks HTTP connections: https://docs.databricks.com/aws/en/query-federation/http
- Connect agents to external services: https://docs.databricks.com/aws/en/generative-ai/agent-framework/external-connection-tools
- Deploy agents on Model Serving: https://docs.databricks.com/gcp/en/generative-ai/agent-framework/deploy-agent
- Databricks Model Context Protocol overview: https://docs.databricks.com/aws/en/generative-ai/mcp
- Databricks-hosted foundation models: https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models
