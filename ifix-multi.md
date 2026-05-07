# Finance Genie Full Multi-Agent Automation Plan

## Goal

Automate the full Finance Genie multi-agent architecture so one operator flow can
provision or validate the full demo path:

- Neo4j MCP secrets and Unity Catalog external MCP connection.
- Neo4j GDS fraud specialist endpoint.
- BEFORE Genie Space availability.
- Databricks Supervisor Agent creation or update.
- Permissions across the supervisor, endpoint, Genie, tables, and MCP
  connection.
- End-to-end graph-first, Genie-second validation.

The current `finance-genie/multi-agent-demo` project deploys only the graph
specialist Model Serving endpoint. The missing automation is the surrounding
Supervisor Agent setup and validation.

## Target Architecture

```text
                         Analyst Question
                               |
                               v
                 +-----------------------------+
                 | Databricks Supervisor Agent |
                 | created/updated by setup    |
                 +-------------+---------------+
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
+-------------------------------+     +----------------------------+
| Graph Specialist Endpoint     |     | BEFORE Genie Space         |
| finance-neo4j-gds-fraud-...   |     | Silver/base Delta tables   |
| deployed by automation        |     | accounts, merchants,       |
+---------------+---------------+     | transactions, account_links |
                |                     +-------------+--------------+
                v                                   |
+-------------------------------+                   |
| Databricks MCP Proxy          |                   |
| UC external MCP connection    |                   |
+---------------+---------------+                   |
                |                                   |
                v                                   |
+-------------------------------+                   |
| AgentCore / Neo4j MCP Server  |                   |
+---------------+---------------+                   |
                |                                   |
                v                                   v
+-------------------------------+     +----------------------------+
| Neo4j Aura + GDS Evidence     |     | Silver-table business      |
| communities, centrality,      |     | impact and account context |
| similarity, transfer density  |     +-------------+--------------+
+---------------+---------------+                   |
                |                                   |
                +----------------+------------------+
                                 |
                                 v
                  Supervisor synthesizes final answer
                  graph evidence + business impact
```

## Assumptions

- `finance-genie/multi-agent-demo` remains the canonical graph-specialist
  implementation.
- The old Gold-table enrichment path remains available as comparison material,
  but is not required for this multi-agent demo.
- The setup should be idempotent. Re-running it should update or validate
  resources instead of creating duplicates.
- Remote endpoint deployment and serverless usage are cost-bearing, so execution
  should be explicit and visible.
- Supervisor Agent setup must be checked against Databricks-supported subagent
  types before implementation is finalized.

## Key Design Decision

Before implementing automation, confirm which Supervisor Agent topology is
supported for this graph specialist.

Preferred topology:

- Supervisor Agent calls the deployed graph-specialist Model Serving endpoint.
- Supervisor Agent calls the BEFORE Genie Space.

Fallback topologies if arbitrary graph-specialist endpoints are not supported:

- Supervisor Agent calls the Neo4j external MCP connection directly.
- Wrap the graph specialist as a Databricks App custom agent and attach that app
  to the Supervisor Agent.
- Build a custom Databricks Apps orchestrator that calls the graph specialist
  endpoint and BEFORE Genie.

The plan should not automate a fragile or unsupported topology.

## Risks

- Supervisor Agent may not support the current graph specialist endpoint as an
  attachable Agent Endpoint.
- Missing `USE CONNECTION`, `CAN QUERY`, Genie access, or table permissions can
  appear as routing failures.
- GDS readiness must be validated before the supervisor is created, otherwise
  the graph specialist can answer schema questions but not fraud-ring discovery
  prompts.
- Weak subagent descriptions can cause the supervisor to route graph questions
  to Genie or silver-table analysis questions to the graph specialist.
- Endpoint deletion is the only reliable serving-cost stop action, so cleanup
  must stay explicit.

## Autonomous Execution Model

The implementation should minimize operator questions by treating `.env`,
documented defaults, and preflight validation as the source of truth.

Allowed autonomous actions:

- Read `.env` and discover Databricks resource IDs.
- Reuse an existing UC external MCP connection when functional validation
  passes.
- Skip secret and connection provisioning when the existing connection works.
- Upload remote job scripts and agent code.
- Run precondition validation.
- Register or update the UC model version.
- Create or update the graph-specialist Model Serving endpoint.
- Poll endpoint readiness with bounded timeouts.
- Run local and remote smoke tests.
- Create or update the Supervisor Agent after the supported topology is
  confirmed.
- Grant non-destructive permissions declared in `.env`.
- Write status and validation artifacts.

Actions that require an explicit flag:

- Creating or rotating MCP secrets.
- Creating, replacing, or mutating the UC external MCP connection.
- Deleting serving endpoints.
- Deleting UC models, MLflow experiments, Genie Spaces, MCP connections, or
  secrets.
- Changing the selected Databricks workspace or profile.
- Running against a production or shared workspace without a validation-only
  preflight.

Automation defaults:

- Validate before creating resources.
- Reuse working resources instead of reprovisioning them.
- Prefer idempotent create-or-update behavior.
- Use bounded timeouts and visible logs.
- Fail closed when auth, workspace, MCP, Genie, table, serving, or GDS checks do
  not pass.

## Phase Checklist

### Phase 1 - Confirm Supported Supervisor Topology

Status: Pending

Checklist:

- Confirm whether Databricks Supervisor Agent can attach the deployed
  graph-specialist Model Serving endpoint.
- If supported, standardize on Supervisor Agent with graph endpoint plus BEFORE
  Genie.
- If unsupported, choose the fallback topology.
- Update `multi-agent.md` with the selected topology and the reason.
- Update `multi-mcp-testplan.md` so its validation phases match the selected
  topology.

Validation:

- A documented decision says exactly which Databricks resource type represents
  the graph specialist in the supervisor.

Notes:

- This is the highest-risk phase because it controls the rest of the
  implementation.

### Phase 2 - Define Full-Architecture Config Contract

Status: Pending

Checklist:

- Add settings for supervisor display name, description, instructions, graph
  tool description, BEFORE Genie Space ID, and validation prompts.
- Add principal settings for demo users, endpoint identity, and supervisor or
  app identity.
- Separate required setup values from optional cleanup values.
- Document which settings are read from `.env`.
- Document which resource IDs are discovered from Databricks.

Validation:

- A fresh operator can create one `.env` and identify every required value.

Notes:

- Keep graph-specialist-only settings separate from supervisor-level settings so
  endpoint deployment can still be tested independently.

### Phase 3 - Add Preflight Validation

Status: Pending

Checklist:

- Validate Databricks authentication and target workspace.
- Validate Unity Catalog catalog, schema, and silver/base tables.
- Validate BEFORE Genie Space exists and is queryable.
- Validate UC external MCP connection exists and is MCP-enabled.
- Validate expected Neo4j MCP tools are discoverable.
- Validate Neo4j GDS evidence is present.
- Validate LLM endpoint access.
- Validate serverless or serving policy availability before deployment.

Validation:

- Preflight fails before deployment if any required architecture component is
  missing.

Notes:

- This phase should catch environment problems before any new remote serving
  revision is created.

### Phase 4 - Automate Graph Specialist Deployment

Status: Pending

Checklist:

- Reuse the existing `finance-genie/multi-agent-demo` deployment flow.
- Keep UC model registration idempotent.
- Keep Model Serving endpoint creation or update idempotent.
- Poll endpoint readiness.
- Run graph-specialist smoke validation.
- Capture endpoint name and status for supervisor setup.

Validation:

- The graph specialist endpoint is `READY`.
- A smoke prompt returns Neo4j-backed candidate evidence.

Notes:

- This phase validates the specialist endpoint only, not the full supervisor
  handoff.

### Phase 5 - Automate Supervisor Creation Or Update

Status: Pending

Checklist:

- Create or update the Supervisor Agent using the selected supported topology.
- Attach or configure the graph specialist path.
- Attach or configure the BEFORE Genie Space.
- Add graph-first, Genie-second routing instructions.
- Add subagent descriptions that clearly separate graph discovery from
  silver-table business analysis.
- Record the supervisor ID, endpoint, and operator-facing test instructions.

Validation:

- The supervisor exists.
- The supervisor has the expected graph and BEFORE Genie resources attached.

Notes:

- If the selected topology is a Databricks Apps orchestrator instead of Agent
  Bricks Supervisor Agent, this phase creates or updates that app instead.

### Phase 6 - Automate Permissions

Status: Pending

Checklist:

- Grant demo users query access to the supervisor.
- Grant required access to the graph specialist endpoint or selected graph
  resource.
- Grant required access to the BEFORE Genie Space.
- Grant required table permissions for the silver/base tables.
- Grant `USE CONNECTION` on the Neo4j MCP connection where needed.
- Validate effective permissions for the configured principals.

Validation:

- Permission checks pass for every configured user or service principal before
  end-to-end testing.

Notes:

- Permission validation should explain which principal is missing which
  privilege.

### Phase 7 - End-To-End Handoff Test

Status: Pending

Checklist:

- Ask a graph-first fraud-ring discovery prompt.
- Confirm the graph path is called first.
- Confirm candidate account IDs are returned.
- Confirm the candidate account IDs are passed to BEFORE Genie.
- Confirm the final answer combines graph evidence with silver-table business
  context.
- Confirm Gold tables and AFTER Genie are not used.

Validation:

- The supervisor trace shows graph-first, BEFORE-Genie-second routing.
- The final answer recommends an investigation priority from combined evidence.

Notes:

- This phase is the proof that the automated architecture works as a
  multi-agent demo, not just as separate working resources.

### Phase 8 - Lifecycle And Cleanup

Status: Pending

Checklist:

- Add a status flow that reports all architecture components.
- Add a validation-only flow that makes no remote changes.
- Add an explicit stop flow for the graph-specialist serving endpoint.
- Preserve UC model, MLflow experiment, MCP connection, secrets, and Genie
  unless explicitly requested.
- Document what each cleanup action deletes and what it preserves.

Validation:

- Operators can inspect, validate, deploy, and stop serving costs without
  accidentally deleting durable setup.

Notes:

- Destructive cleanup should require explicit confirmation.

## Completion Criteria

- One documented operator flow sets up the full architecture.
- The setup is idempotent.
- The selected Supervisor topology is supported by Databricks.
- Preflight validation catches missing auth, MCP, Genie, table, serving, and GDS
  prerequisites.
- Graph-specialist endpoint deployment is automated and smoke-tested.
- Supervisor creation or update is automated.
- Permissions are applied and validated.
- End-to-end validation proves graph-first, BEFORE-Genie-second routing.
- Cleanup can stop serving costs without removing durable setup by accident.
