# Finance Genie Multi-MCP Test Plan

## Goal

Validate the Finance Genie Neo4j GDS fraud specialist and its multi-agent MCP
demo flow before using it in a Databricks Supervisor Agent.

The tested flow is:

1. Local project validation.
2. Optional local in-process agent smoke test against Databricks MCP.
3. Optional local HTTP server lifecycle test.
4. MCP secret and UC external MCP connection validation.
5. Remote Databricks job upload and precondition validation.
6. Model logging, Unity Catalog registration, and Model Serving deployment.
7. Endpoint readiness polling.
8. Remote endpoint smoke test.
9. Supervisor Agent handoff validation with Neo4j first and BEFORE Genie second.

## Assumptions

- `finance-genie/multi-agent-demo` is the graph-only specialist endpoint.
- The graph specialist calls only the Neo4j external MCP connection.
- The Databricks Supervisor Agent is configured separately and calls:
  - the graph specialist endpoint for Neo4j GDS fraud candidates;
  - the BEFORE Genie Space for silver/base-table analysis.
- The UC external MCP connection owns the upstream AgentCore or Neo4j secrets.
- The graph specialist endpoint receives only `LLM_ENDPOINT_NAME` and
  `UC_CONNECTION_NAME` at serving time.
- Remote tests require `finance-genie/multi-agent-demo/.env`, Databricks auth,
  MCP credentials, and a reachable workspace.

## Risks

- A missing `.env` or Databricks auth configuration blocks all live tests.
- A missing or drifted UC HTTP connection blocks MCP tool discovery.
- GDS may not have run even if the graph is reachable, which makes fraud-ring
  candidate prompts weak or invalid.
- Deleting a remote serving endpoint is the only reliable stop action for
  serving cost control, so destructive remote-stop tests must be explicit.
- Local live tests still call remote Databricks services because the specialist
  uses the Databricks MCP proxy.

## Test Order

### Phase 1 - Local Static Validation

Status: Complete

Checklist:

- Complete: Run shell syntax checks for lifecycle scripts.
- Complete: Run Python syntax checks for agent, jobs, setup, validation, and
  local server modules.
- Pending: Confirm no generated `.venv` or `__pycache__` artifacts remain.

Validation:

- Complete: `./scripts/test_local.sh` exits 0.

Notes:

- This phase does not require `.env`, Databricks auth, or network access.

### Phase 2 - Local Live Agent Validation

Status: Blocked

Checklist:

- Blocked: Confirm `.env` exists with Databricks profile, model endpoint, and
  UC MCP connection values.
- Blocked: Run local in-process agent smoke test.
- Blocked: Confirm the response contains a Neo4j MCP tool result.
- Blocked: Confirm the response returns compact fraud-candidate language.

Validation:

- Blocked: `./scripts/test_local.sh --agent-smoke` failed because the
  Databricks SDK could not configure default credentials.

Notes:

- This phase imports the agent and initializes MCP tools, so it requires
  Databricks auth and `USE CONNECTION` on the UC external MCP connection.

### Phase 3 - Local Server Lifecycle

Status: Blocked

Checklist:

- Complete: Start command writes PID and log locations.
- Blocked: Call `GET /health`.
- Blocked: Call `POST /responses` with a graph-candidate prompt.
- Complete: Stop command handles an already-exited process and removes the PID
  file.
- Pending: Confirm generated local artifacts are removed.

Validation:

- Blocked: `./scripts/start_local.sh` process exited during startup because the
  Databricks SDK could not configure default credentials.
- Blocked: The server response is successful for `/health` and tool-backed for
  `/responses`.

Notes:

- `/responses` requires the same Databricks/MCP access as Phase 2.

### Phase 4 - MCP Secrets And UC Connection

Status: Blocked

Checklist:

- Blocked: Confirm `.mcp-credentials.json` exists when this directory owns MCP
  connection secrets.
- Blocked: Store AgentCore OAuth values in `MCP_SECRET_SCOPE`.
- Blocked: Provision or validate the UC HTTP connection.
- Blocked: Confirm the connection has the MCP flag enabled.
- Blocked: Confirm demo users and endpoint identity have `USE CONNECTION`.

Validation:

- Blocked: `./setup_secrets.sh --profile DEFAULT` failed because
  `finance-genie/multi-agent-demo/.env` is missing.
- Pending: `uv run setup/provision_connection.py --profile <profile>` exits 0.

Notes:

- If `finance-genie/neo4j-mcp-demo` already owns the connection and secret
  scope, skip the secret write and only validate/reuse the connection.

### Phase 5 - Remote Precondition Validation

Status: Blocked

Checklist:

- Blocked: Upload remote job scripts and agent code.
- Blocked: Validate silver/base tables exist.
- Blocked: Validate MCP tool discovery through Databricks.
- Blocked: Validate a read-only GDS readiness query can execute through MCP.

Validation:

- Blocked: `./scripts/start_remote.sh --endpoint-timeout-min 1` failed before
  remote calls because `.env` is missing.

Notes:

- This phase must run before deployment so missing graph/GDS prerequisites fail
  before registering a new model version.

### Phase 6 - Remote Model Serving Deployment

Status: Blocked

Checklist:

- Blocked: Log the agent with MLflow code-based logging.
- Blocked: Register the model to Unity Catalog.
- Blocked: Deploy with `databricks.agents.deploy()`.
- Blocked: Declare LLM endpoint and MCP connection resources for automatic
  authentication.
- Blocked: Poll endpoint readiness until `READY`.

Validation:

- Blocked: `./scripts/deploy_all.sh --skip-secrets --skip-connection
  --skip-local-test --skip-smoke-test` failed before remote calls because
  `.env` is missing.

Notes:

- Updates should keep the same UC model name and endpoint name for zero-downtime
  rollout behavior.

### Phase 7 - Remote Endpoint Smoke Test

Status: Blocked

Checklist:

- Blocked: Run the Databricks job smoke test.
- Blocked: Run a local SDK query against the remote endpoint.
- Blocked: Confirm a tool result is present.
- Blocked: Confirm graph-candidate evidence is present.

Validation:

- `uv run python -m cli submit 02_validate_endpoint.py` exits 0.
- Blocked: `./scripts/test_remote.sh` failed before remote calls because
  `.env` is missing.

Notes:

- This phase validates the deployed endpoint, not the Supervisor Agent.

### Phase 8 - Supervisor Agent Handoff Test

Status: Blocked

Checklist:

- Blocked: Configure Supervisor Agent with graph specialist endpoint and BEFORE
  Genie Space.
- Blocked: Ask a graph-first prompt that requires fraud-ring discovery.
- Blocked: Confirm the Supervisor calls the graph specialist first.
- Blocked: Confirm the Supervisor passes candidate account IDs to BEFORE Genie.
- Blocked: Confirm final answer cites graph evidence and silver-table business
  impact, without gold tables or AFTER Genie.

Validation:

- Supervisor trace shows both subagent calls in the expected order.
- Final answer recommends an investigation priority from combined evidence.

Notes:

- Supervisor Agent setup is outside `finance-genie/multi-agent-demo`; this
  phase validates integration.

### Phase 9 - Remote Stop

Status: Blocked

Checklist:

- Blocked: Delete the graph-specialist serving endpoint when the demo is done.
- Blocked: Confirm endpoint no longer exists.
- Blocked: Confirm UC model, MLflow experiment, MCP connection, and secrets are
  intentionally preserved.

Validation:

- Blocked: `./scripts/stop_remote.sh --yes` failed before deletion because
  `.env` is missing.
- Pending: A follow-up endpoint readiness check reports endpoint not found.

Notes:

- Do not run this phase automatically during validation unless remote deletion
  is explicitly intended.

## Completion Criteria

- Local static validation passes.
- Live local and remote tests pass when `.env`, credentials, and Databricks
  access are available.
- Remote deployment creates or updates the Model Serving endpoint.
- Endpoint smoke tests prove Neo4j MCP tool use and GDS candidate output.
- Supervisor Agent integration proves graph-first, BEFORE-Genie-second routing.
- Remote stop deletes only the serving endpoint.

## Current Test Run

Status: Blocked

Results:

- Complete: Local static validation passed with `./scripts/test_local.sh`.
- Blocked: Local live smoke failed because Databricks default auth is not
  configured.
- Blocked: Local server lifecycle starts and stops safely, but server startup
  fails because Databricks default auth is not configured.
- Blocked: MCP secret setup failed because `.env` is missing.
- Blocked: Remote precondition validation failed before remote calls because
  `.env` is missing.
- Blocked: Remote deployment validation failed before remote calls because
  `.env` is missing.
- Blocked: Remote endpoint smoke validation failed before remote calls because
  `.env` is missing.
- Blocked: Supervisor Agent handoff validation requires a deployed graph
  specialist endpoint and configured Supervisor Agent.
- Blocked: Remote stop failed before deletion because `.env` is missing.

Next required action:

- Create `finance-genie/multi-agent-demo/.env` from `.env.sample`.
- Configure Databricks auth or set `DATABRICKS_PROFILE` in `.env`.
- Provide `.mcp-credentials.json` if this directory owns the UC external MCP
  connection secrets.
- Re-run this plan from Phase 2.
