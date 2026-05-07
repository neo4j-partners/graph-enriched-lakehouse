# Finance Genie Neo4j GDS Fraud Specialist

This directory deploys the graph-only specialist used by the Finance Genie
Supervisor Agent demo.

The specialist calls Neo4j through the Databricks Unity Catalog external MCP
proxy and returns compact GDS-backed fraud-ring candidates. It does not call
Genie, query Delta tables directly, or depend on graph-enriched gold tables.

## Demo Role

Use this endpoint as one subagent in a Databricks Supervisor Agent:

- `finance-genie/multi-agent-demo`: Neo4j/GDS fraud candidate retrieval.
- BEFORE Genie Space: silver/base-table analysis over `accounts`, `merchants`,
  `transactions`, and `account_links`.

The supervisor calls this endpoint first, then passes returned account IDs and
graph rationale to BEFORE Genie for business impact analysis.

## Files

- `finance_graph_supervisor_agent.py`: graph-only LangGraph `ResponsesAgent`.
- `jobs/00_validate_demo_preconditions.py`: base-table, MCP, and GDS readiness
  checks.
- `jobs/01_deploy_agent.py`: logs, registers, and deploys the graph specialist.
- `jobs/02_validate_endpoint.py`: smoke test for tool-backed GDS candidate
  retrieval.
- `setup_secrets.sh`: stores AgentCore OAuth credentials used by the UC external
  MCP connection.
- `presenter-script.md`: live demo flow.
- `demo-agent.md`: design notes and Supervisor Agent handoff guidance.

## Setup

From this directory:

```bash
cp .env.sample .env
```

Fill in `.env` with the Databricks workspace, model registration, serving
endpoint, and MCP connection values.

If this directory owns the Neo4j MCP connection secrets, copy the
AgentCore-generated `.mcp-credentials.json` into this directory and run:

```bash
./setup_secrets.sh --profile <profile-name>
```

This writes the OAuth values into `MCP_SECRET_SCOPE`. The deployed endpoint does
not read those secrets directly. The Unity Catalog HTTP connection reads them
when Databricks calls the external MCP server.

If `finance-genie/neo4j-mcp-demo` already provisioned the same connection and
secret scope, reuse that setup and skip this secret step.

## Operator Flow

The safest order is:

1. Validate local syntax and packaging.
2. Optionally run the agent locally against the Databricks MCP proxy.
3. Store MCP connection secrets if this directory owns them.
4. Provision or validate the UC external MCP connection.
5. Upload remote jobs and agent code.
6. Run remote preconditions for base tables, MCP discovery, and GDS readiness.
7. Log, register, and deploy the Model Serving endpoint.
8. Wait until the endpoint is READY.
9. Run both the remote smoke-test job and a local SDK query against the endpoint.

Run these after the base Finance Genie tables have been loaded into Unity
Catalog, Neo4j ingest has completed, and GDS has run in Neo4j.

End-to-end deployment:

```bash
./scripts/deploy_all.sh --profile <profile-name> --compute serverless
```

If the MCP connection and secrets already exist, skip those setup steps:

```bash
./scripts/deploy_all.sh --profile <profile-name> --skip-secrets --skip-connection
```

Manual remote flow:

```bash
./scripts/test_local.sh
./setup_secrets.sh --profile <profile-name>
uv run setup/provision_connection.py --profile <profile-name>
uv run python -m cli upload --all
uv run python -m cli submit 00_validate_demo_preconditions.py
uv run python -m cli submit 01_deploy_agent.py
uv run validation/validate_endpoint.py
uv run python -m cli submit 02_validate_endpoint.py
./scripts/test_remote.sh --profile <profile-name>
```

The validation job is intentionally first. It catches missing base tables, a
broken MCP connection, or missing GDS evidence before registering a model or
creating a serving endpoint revision.

## Start And Stop

Local development server:

```bash
./scripts/start_local.sh
./scripts/stop_local.sh
```

The local server exposes `GET /health` and `POST /responses` on port `8787` by
default. It still uses your Databricks auth and the remote MCP proxy.

Remote endpoint:

```bash
./scripts/start_remote.sh --profile <profile-name> --compute serverless
./scripts/stop_remote.sh --profile <profile-name> --yes
```

`stop_remote.sh` deletes the Model Serving endpoint to stop serving costs. It
does not delete the UC model, MLflow experiment, MCP connection, or secrets.

## Permissions

The deployed endpoint identity needs:

- Query access to the LLM serving endpoint in `LLM_ENDPOINT_NAME`.
- `USE CONNECTION` on the Unity Catalog HTTP connection in
  `UC_CONNECTION_NAME`.

The Supervisor Agent or demo user needs:

- Query access to this graph-specialist serving endpoint.
- Access to the BEFORE Genie Space.
- Access to the silver/base Delta tables behind the BEFORE Genie Space.
- Any workspace permissions required to use the Supervisor Agent tile.

## What This Replaces

This demo replaces the old runtime dependency on graph-enriched gold tables. It
does not require `gold_accounts`, `gold_account_similarity_pairs`,
`gold_fraud_ring_communities`, the AFTER Genie Space, `03_pull_gold_tables.py`,
or `04_validate_gold_tables.py`.
