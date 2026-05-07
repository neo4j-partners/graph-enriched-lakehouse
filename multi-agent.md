# Finance Genie Multi-Agent Rewrite Plan

## Goal

Rewrite the Finance Genie multi-agent demo so it demonstrates an alternative to
persisting Neo4j GDS findings into graph-enriched gold Delta tables.

The new flow is:

1. A Databricks Supervisor Agent receives the analyst question.
2. The supervisor calls the Neo4j GDS fraud specialist endpoint from
   `finance-genie/multi-agent-demo`.
3. The graph specialist calls the Neo4j MCP server through the Databricks Unity
   Catalog external MCP proxy and retrieves likely fraud-ring candidates from
   GDS-backed graph evidence.
4. The supervisor passes the candidate account IDs and graph rationale to the
   BEFORE Genie Space.
5. BEFORE Genie analyzes those accounts with the silver/base Delta tables:
   `accounts`, `merchants`, `transactions`, and `account_links`.
6. The supervisor synthesizes graph evidence plus silver-table business impact.

This proves that the same investigation outcome can be reached without running
the old `03_pull_gold_tables.py` and `04_validate_gold_tables.py` path.

## Current Architecture Decision

`finance-genie/multi-agent-demo` is the canonical implementation for the graph
specialist endpoint. It is no longer a code-first supervisor and it no longer
calls Genie directly.

The Databricks Supervisor Agent is configured separately. It should have two
subagents:

- **Neo4j GDS fraud specialist endpoint**: deployed from
  `finance-genie/multi-agent-demo`; finds likely fraud-ring candidates from
  Neo4j MCP and GDS evidence.
- **BEFORE Genie Space**: analyzes returned account IDs against silver/base
  Finance Genie tables.

## Assumptions

- Neo4j still receives the base Finance Genie graph and runs GDS, so account
  nodes and relationships contain the GDS evidence needed for fraud discovery.
- The graph specialist uses only the Unity Catalog external MCP connection. It
  does not connect directly to Genie and does not read gold tables.
- Candidate handoff is prompt-based for the live demo. The graph specialist
  returns compact account IDs and evidence, and the supervisor includes those
  IDs in the follow-up prompt to BEFORE Genie.
- The UC external MCP connection usually owns the upstream AgentCore or Neo4j
  credentials. This demo can store those secrets for the connection, but the
  deployed model should receive only the UC connection name.
- The old graph-enriched gold-table path can stay in `finance-genie/automated`
  as a comparison flow, but it is not a prerequisite for this demo.

## Risks

- Missing `USE CONNECTION` on the Neo4j MCP UC connection will make the graph
  specialist fail even if the endpoint deploys successfully.
- Missing query access to the graph specialist endpoint or BEFORE Genie Space
  will make the Supervisor Agent appear to route incorrectly.
- If GDS has not run in Neo4j, MCP can still answer schema questions but cannot
  return credible fraud-ring candidates.
- If the graph specialist returns too many raw account IDs, the supervisor prompt
  becomes noisy. Keep live-demo candidate payloads compact.
- Weak Supervisor Agent subagent descriptions can route silver-table analysis to
  the graph specialist or graph topology questions to Genie.

## Phase Checklist

### Phase 1 - Rewrite The Persistent Plan

Status: Complete

Checklist:

- Complete: `multi-agent.md` describes the new Supervisor Agent flow.
- Complete: `finance-genie/multi-agent-demo` is documented as the graph-only
  specialist implementation.
- Complete: AFTER Genie and gold tables are removed from the required path.
- Complete: Secrets and permissions are split between MCP connection access,
  endpoint access, and BEFORE Genie access.

Validation:

- Complete: Search for stale AFTER/gold references only finds language that
  marks those assets as not required or old-path comparisons.

Notes:

- The old gold-table flow remains useful as a before/after comparison, but not
  as part of this demo's setup.

### Phase 2 - Replace The Graph Specialist Implementation

Status: Complete

Checklist:

- Complete: Rewrite the agent as `Finance Neo4j GDS Fraud Specialist`.
- Complete: Remove direct Genie SDK usage and `GENIE_SPACE_ID_*` settings.
- Complete: Keep dynamic Neo4j MCP tool discovery through the UC external MCP
  proxy.
- Complete: Update system instructions for compact fraud-candidate retrieval.
- Complete: Keep all graph work read-only and aggregate-first.

Validation:

- Complete: Static search confirms no direct Genie calls remain in
  `finance-genie/multi-agent-demo`.
- Pending: Endpoint smoke test confirms an MCP tool call result is present.

### Phase 3 - Rewrite Config, Secrets, And Setup

Status: Complete

Checklist:

- Complete: Rewrite `.env.sample` and `config.py` around graph-specialist
  settings.
- Complete: Keep AgentCore/MCP secret setup for creating or refreshing the UC
  external MCP connection's backing secrets.
- Complete: Remove required Genie Space IDs from this directory.
- Complete: Document endpoint identity requirements: LLM serving endpoint access
  and `USE CONNECTION` on the Neo4j MCP connection.
- Complete: Document demo-user requirements: Supervisor Agent access, graph
  endpoint query access, BEFORE Genie access, and silver-table permissions.

Validation:

- Complete: Setup docs explain which secrets are created here and which are
  consumed through the UC connection.

### Phase 4 - Rewrite Jobs And Validation

Status: Complete

Checklist:

- Complete: Rewrite preconditions for base table checks, MCP discovery, and GDS
  readiness.
- Complete: Remove gold-table checks and AFTER Genie validation.
- Complete: Rewrite deployment so only graph-specialist environment variables
  are injected.
- Complete: Rewrite endpoint validation around GDS candidate retrieval.

Validation:

- Pending: Precondition job fails clearly when MCP tools are missing.
- Pending: Endpoint validation confirms graph-tool use and candidate evidence.

### Phase 5 - Rewrite Demo Documentation

Status: Complete

Checklist:

- Complete: Rewrite `README.md` as the graph-specialist operator guide.
- Complete: Rewrite `demo-agent.md` as the graph-specialist design note.
- Complete: Rewrite `presenter-script.md` around the Supervisor Agent flow.
- Complete: Add troubleshooting for secrets, permissions, MCP discovery, missing
  GDS evidence, and routing mistakes.

Validation:

- Complete: A new operator can deploy the graph specialist and understand how it
  plugs into the Supervisor Agent.

### Phase 6 - Supervisor Agent Handoff

Status: Complete

Checklist:

- Complete: Document the Supervisor Agent subagent descriptions.
- Complete: Document graph-first, Genie-second routing guidance.
- Complete: Add example questions that require both subagents.
- Complete: Document expected response evidence and final synthesis behavior.

Validation:

- Pending: Combined prompt traces show graph endpoint plus BEFORE Genie calls.

## Completion Criteria

- `multi-agent.md` reflects the new architecture.
- `finance-genie/multi-agent-demo` is a complete graph-only specialist.
- The directory no longer requires AFTER Genie or graph-enriched gold tables.
- Secrets and permissions are clear for MCP, endpoint, Supervisor Agent, and
  BEFORE Genie access.
- Validation proves Neo4j MCP can return GDS-backed fraud candidates.
- Demo documentation shows how the Supervisor Agent reaches the same business
  conclusion without enhancing gold tables.
