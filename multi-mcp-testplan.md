# Finance Genie Multi-MCP Test Plan

## Goal

Validate the Finance Genie Neo4j GDS fraud specialist and its multi-agent MCP
demo flow before using it in a Databricks Supervisor Agent.

The target flow is:

1. The Supervisor Agent calls the Neo4j graph specialist endpoint first.
2. The graph specialist calls the Neo4j external MCP server through Databricks.
3. The graph specialist returns GDS-backed fraud-ring candidates, compact
   account IDs, graph evidence, and a BEFORE Genie prompt.
4. The Supervisor Agent calls the BEFORE Genie Space with the candidate account
   IDs.
5. BEFORE Genie combines those IDs with silver/base tables for business context.

This proves an alternative to enriching gold tables with GDS findings. GDS stays
in Neo4j, Databricks governs access through external MCP, and Genie analyzes the
candidate IDs against silver/base data.

## Current Status

Date: 2026-05-06

Profile: `azure-rk-knight`

Overall status: Local live path works. Remote deployment is paused before model
deployment.

What is working:

- `finance-genie/multi-agent-demo/.env` exists.
- `finance-genie/multi-agent-demo/.mcp-credentials.json` exists.
- Local static validation passes with `./scripts/test_local.sh`.
- The graph specialist can authenticate with Databricks using
  `azure-rk-knight`.
- The Databricks external MCP proxy can discover Neo4j tools.
- Direct read-only Cypher through MCP works and returned `account_count: 25000`.
- Local in-process agent smoke test works with
  `./scripts/test_local.sh --agent-smoke`.
- The in-process agent returned Neo4j-backed fraud-ring candidates and a BEFORE
  Genie follow-up prompt.
- Foreground local HTTP server testing works:
  - `GET /health` returned `{"status": "ok"}`.
  - `POST /responses` returned a tool-backed graph answer.

What is broken or unproven:

- Persistent background local server behavior is not reliable in this command
  runner. The foreground server works, but `start_local.sh` background processes
  can be torn down after the command wrapper exits.
- `setup/provision_connection.py --profile azure-rk-knight` did not finish
  during the interrupted `deploy_all.sh` run. It was still running silently when
  the user interrupted the turn.
- Remote Databricks job upload has not been completed in the current run.
- Remote precondition validation has not been run to completion.
- MLflow model logging, UC model registration, Model Serving deployment,
  endpoint readiness polling, and remote endpoint smoke tests have not been run
  to completion.
- Supervisor Agent graph-first, BEFORE-Genie-second routing has not been tested.

What was stopped:

- The interrupted `deploy_all.sh` process was still alive after the user
  interruption.
- These processes were inspected and stopped:
  - `bash ./scripts/deploy_all.sh --profile azure-rk-knight --compute serverless --skip-secrets --endpoint-timeout-min 45`
  - `uv run setup/provision_connection.py --profile azure-rk-knight`
  - `.venv/bin/python3 setup/provision_connection.py --profile azure-rk-knight`

## What Was Tried

- Ran local static validation.
- Ran local in-process agent smoke testing.
- Inspected the installed `ChatDatabricks` signature and confirmed it supports
  `workspace_client`.
- Patched `finance_graph_supervisor_agent.py` so the same profiled
  `WorkspaceClient` is passed to both the MCP client and `ChatDatabricks`.
- Inspected MCP tool schemas and found:
  - `neo4j-mcp-server-target___get-schema`
  - `neo4j-mcp-server-target___list-gds-procedures`
  - `neo4j-mcp-server-target___read-cypher`
- Found that the discovery tools require a `properties` argument.
- Patched the agent instructions to call discovery tools with
  `{"properties": {}}` when no filters are needed.
- Directly called MCP read-only Cypher through `DatabricksMCPClient`.
- Started the local HTTP server in foreground and tested `/health` and
  `/responses`.
- Patched `scripts/local_agent_server.py` to lazy-load the agent on `POST`, so
  `/health` does not wait on Databricks MCP and model initialization.
- Patched `scripts/start_local.sh` to use unbuffered Python and surface early
  startup failures from the log.
- Started `deploy_all.sh` with `--profile azure-rk-knight --compute serverless
  --skip-secrets --endpoint-timeout-min 45`.
- Stopped that deployment after it was interrupted during UC connection
  provisioning/validation.

## Current Issue

The main issue is no longer local auth, MCP access, or graph retrieval. Those
are working.

The active issue is remote setup sequencing. `deploy_all.sh` tried to run
`setup/provision_connection.py` before upload, precondition validation, and
deployment. In this run that provisioning step produced no output for more than
a minute and was still running when interrupted.

Because direct MCP tool discovery and read-only Cypher already work, the
existing UC external MCP connection appears functionally valid. For this
workspace, skip connection provisioning and continue with remote precondition
validation.

Do not re-architect yet. First prove whether the graph specialist can deploy as
a remote Model Serving endpoint and call the Neo4j MCP connection from the
serving runtime. Re-architecture should happen only if remote endpoint
deployment, remote MCP access, or Supervisor Agent attachment fails for a
Databricks-supported reason.

After the remote endpoint path is proven, implement `ifix-multi.md` to automate
the full architecture: Supervisor Agent creation or update, permissions,
end-to-end handoff validation, status reporting, and cleanup.

## Autonomous Execution Policy

The setup should run as autonomously as possible by using explicit defaults and
preflight checks instead of interactive operator questions.

Allowed autonomous actions:

- Read `.env` and discovered Databricks resource IDs.
- Reuse the existing UC external MCP connection when functional MCP validation
  passes.
- Skip secret and connection provisioning when `--skip-secrets` and
  `--skip-connection` are set.
- Upload remote job scripts and agent code.
- Run remote precondition validation.
- Register or update the UC model version.
- Create or update the graph-specialist Model Serving endpoint.
- Poll endpoint readiness.
- Run remote smoke tests.
- Create or update the Supervisor Agent after `ifix-multi.md` confirms the
  supported topology.
- Grant missing non-destructive permissions declared in `.env`.
- Write status and validation artifacts.

Actions that should still require an explicit flag:

- Creating or rotating MCP secrets.
- Creating, replacing, or mutating the UC external MCP connection.
- Deleting serving endpoints.
- Deleting UC models, MLflow experiments, Genie Spaces, MCP connections, or
  secrets.
- Changing the selected Databricks workspace or profile.
- Running in a production or shared workspace without a dry-run preflight.

Automation defaults:

- Prefer validation-only checks before resource creation.
- Prefer reuse over reprovisioning when a resource already works.
- Prefer idempotent create-or-update behavior over delete-and-create behavior.
- Prefer bounded timeouts with useful logs over silent waits.
- Fail closed when required auth, workspace, MCP, Genie, table, or GDS checks do
  not pass.

## Test Order

### Phase 1 - Local Static Validation

Status: Complete

Checklist:

- Complete: Run shell syntax checks for lifecycle scripts.
- Complete: Run Python syntax checks for agent, jobs, setup, validation, and
  local server modules.
- Pending: Confirm no generated `.venv`, `.local`, `mlflow.db`, or
  `__pycache__` artifacts remain after final testing.

Validation:

- Complete: `./scripts/test_local.sh` exits 0.

### Phase 2 - Local Live Agent Validation

Status: Complete

Checklist:

- Complete: Confirm `.env` exists.
- Complete: Confirm `.mcp-credentials.json` exists.
- Complete: Run local in-process agent smoke test.
- Complete: Confirm the response contains Neo4j MCP tool results.
- Complete: Confirm the response returns compact fraud-candidate language and a
  BEFORE Genie follow-up prompt.

Validation:

- Complete: `./scripts/test_local.sh --agent-smoke` exits 0.
- Complete: Direct MCP read-only Cypher query returned `account_count: 25000`.

### Phase 3 - Local Server Lifecycle

Status: Partially Complete

Checklist:

- Complete: Foreground server starts.
- Complete: `GET /health` succeeds.
- Complete: `POST /responses` succeeds and returns graph evidence.
- Complete: Stop command handles an already-exited process and removes the PID
  file.
- Unproven: Persistent background process lifetime from `start_local.sh` inside
  this command-runner environment.

Validation:

- Complete: Foreground server on `127.0.0.1:8788` returned
  `{"status": "ok"}`.
- Complete: Foreground `/responses` returned a Neo4j-backed fraud-ring
  candidate answer.

Notes:

- The background start script may work in a normal terminal. In this tool
  environment, the process can be killed after the command wrapper exits.

### Phase 4 - MCP Secrets And UC Connection

Status: Partially Complete

Checklist:

- Complete: `.mcp-credentials.json` exists.
- Not rerun: Secret write, because the user stated `.env` and secrets are
  created.
- Complete by functional test: Existing UC external MCP connection supports tool
  discovery and read-only Cypher.
- Interrupted: `setup/provision_connection.py --profile azure-rk-knight`.
- Deferred: Do not debug provisioning before remote endpoint proof unless MCP
  access fails in the remote job or serving runtime.
- Pending: Confirm endpoint service principal has the required resource access
  after deployment.

Validation:

- Complete: MCP tool discovery found schema discovery, GDS procedure discovery,
  and read-only Cypher.
- Complete: Read-only Cypher through MCP returned `account_count: 25000`.
- Deferred: A bounded, standalone run of `setup/provision_connection.py` is only
  needed if remote runtime MCP access fails or connection drift is suspected.

### Phase 5 - Remote Precondition Validation

Status: Not Started In Current Run

Checklist:

- Pending: Upload remote job scripts and agent code.
- Pending: Validate silver/base tables exist.
- Pending: Validate MCP tool discovery from Databricks job runtime.
- Pending: Validate read-only GDS readiness query from Databricks job runtime.

Validation:

- Pending: `uv run python -m cli submit --compute serverless
  00_validate_demo_preconditions.py` exits 0.

### Phase 6 - Remote Model Serving Deployment

Status: Not Started In Current Run

Checklist:

- Pending: Log the agent with MLflow code-based logging.
- Pending: Register the model to Unity Catalog.
- Pending: Deploy with `databricks.agents.deploy()`.
- Pending: Declare LLM endpoint and MCP connection resources.
- Pending: Poll endpoint readiness until `READY`.

Validation:

- Pending: `./scripts/deploy_all.sh --profile azure-rk-knight --compute
  serverless --skip-secrets --skip-connection --endpoint-timeout-min 45`
  reaches endpoint readiness.

Notes:

- The current run did not reach this phase.
- This phase intentionally skips connection provisioning because local MCP
  functional validation already proved the existing UC external MCP connection.

### Phase 7 - Remote Endpoint Smoke Test

Status: Not Started In Current Run

Checklist:

- Pending: Run the Databricks job smoke test.
- Pending: Run a local SDK query against the remote endpoint.
- Pending: Confirm a tool result is present.
- Pending: Confirm graph-candidate evidence is present.

Validation:

- Pending: `uv run python -m cli submit 02_validate_endpoint.py` exits 0.
- Pending: `./scripts/test_remote.sh --profile azure-rk-knight` exits 0.

### Phase 8 - Supervisor Agent Handoff Test

Status: Blocked On Remote Endpoint

Checklist:

- Pending: After the remote endpoint smoke test passes, implement the
  automation plan in `ifix-multi.md`.
- Pending: Confirm the Databricks-supported topology for connecting the graph
  specialist to the Supervisor Agent.
- Pending: Configure Supervisor Agent with graph specialist endpoint and BEFORE
  Genie Space.
- Pending: Ask a graph-first prompt that requires fraud-ring discovery.
- Pending: Confirm the Supervisor calls the graph specialist first.
- Pending: Confirm the Supervisor passes candidate account IDs to BEFORE Genie.
- Pending: Confirm final answer cites graph evidence and silver-table business
  impact, without gold tables or AFTER Genie.

Validation:

- Pending: Supervisor trace shows both subagent calls in the expected order.
- Pending: Final answer recommends investigation priority from combined graph
  and silver-table evidence.

### Phase 9 - Remote Stop

Status: Not Run

Checklist:

- Pending: Delete the graph-specialist serving endpoint when intentionally done.
- Pending: Confirm endpoint no longer exists.
- Pending: Confirm UC model, MLflow experiment, MCP connection, and secrets are
  intentionally preserved.

Validation:

- Pending: `./scripts/stop_remote.sh --profile azure-rk-knight --yes` deletes
  only the serving endpoint.

Notes:

- Do not run this automatically during validation. Endpoint deletion is a
  deliberate cost-control and cleanup action.

## Next Required Action

Continue the current implementation path and skip connection provisioning for
this workspace. Because direct MCP tool discovery and Cypher already pass, start
with remote precondition validation and deployment:

```bash
cd finance-genie/multi-agent-demo
./scripts/deploy_all.sh --profile azure-rk-knight --compute serverless --skip-secrets --skip-connection --endpoint-timeout-min 45
```

This avoids the currently suspicious provisioning step and tests the actual
remote path: upload, Databricks precondition job, model registration, Model
Serving deployment, readiness, and remote smoke tests.

After the graph-specialist endpoint is deployed and smoke-tested, implement
`ifix-multi.md`.

Re-architect only if:

- Remote Model Serving deployment fails because the agent shape is unsupported.
- The serving endpoint cannot access the UC MCP connection even though local MCP
  access works.
- Supervisor Agent cannot attach or invoke the graph specialist through a
  supported Databricks resource type.
- Supervisor traces cannot prove graph-first, BEFORE-Genie-second routing.
