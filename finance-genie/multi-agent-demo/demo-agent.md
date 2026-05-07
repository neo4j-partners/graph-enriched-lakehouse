# Finance Genie Neo4j GDS Fraud Specialist

## Goal

Provide the graph-only specialist endpoint for the Finance Genie Supervisor
Agent demo.

The endpoint retrieves potential fraud-ring candidates from Neo4j GDS evidence
through MCP. It returns compact account IDs, graph signals, and a recommended
BEFORE Genie follow-up prompt. The Supervisor Agent then asks BEFORE Genie to
analyze those accounts against silver/base tables.

## Architecture

- Neo4j contains the Finance Genie property graph and GDS outputs.
- Databricks exposes Neo4j tools through a Unity Catalog external MCP
  connection.
- This directory deploys a Databricks Model Serving agent that uses only that
  MCP connection.
- A Databricks Supervisor Agent calls this endpoint first, then calls the BEFORE
  Genie Space.

This is deliberately different from the old gold-table enhancement path. The
GDS findings stay in Neo4j for this demo.

## Specialist Behavior

The graph specialist should:

- discover MCP tools dynamically at runtime;
- use schema discovery before writing Cypher when needed;
- run only read-only graph queries;
- retrieve likely fraud-ring candidates from community, centrality, similarity,
  transfer-density, and merchant-overlap signals;
- cap returned account IDs to a demo-safe set;
- return evidence in a compact format suitable for a Supervisor Agent prompt;
- include a recommended BEFORE Genie follow-up prompt over the selected account
  IDs.

The graph specialist should not:

- call Genie directly;
- query SQL warehouses or Delta tables;
- depend on gold tables or AFTER Genie;
- expose large raw account dumps;
- mutate Neo4j data.

## Required Setup

Prerequisites:

- Finance Genie base tables exist in Unity Catalog:
  `accounts`, `merchants`, `transactions`, and `account_links`.
- Neo4j ingest has loaded the base graph.
- GDS has run in Neo4j and written properties or relationships that the MCP
  server can query.
- The Unity Catalog HTTP connection named by `UC_CONNECTION_NAME` is MCP-enabled.
- The endpoint identity has access to the LLM endpoint and `USE CONNECTION` on
  the MCP connection.

Secrets:

- AgentCore or upstream MCP credentials are stored in `MCP_SECRET_SCOPE`.
- The UC external MCP connection uses those secrets.
- The deployed graph specialist receives only `UC_CONNECTION_NAME` and
  `LLM_ENDPOINT_NAME`.
- Genie Space IDs are not secrets for this endpoint because this endpoint does
  not call Genie.

## Supervisor Agent Handoff

Use this graph specialist as one Supervisor Agent subagent.

Graph-specialist subagent description:

```text
Neo4j GDS fraud specialist for Finance Genie. Use this endpoint first for fraud-ring discovery, graph topology, communities, centrality, similarity, transfer density, shared merchant patterns, and read-only Cypher over the Neo4j property graph. It returns compact candidate account IDs and graph evidence for downstream silver-table analysis.
```

BEFORE Genie subagent description:

```text
Finance Genie BEFORE space over silver/base tables. Use this Genie Space after graph candidates are known to analyze selected account IDs across accounts, merchants, transactions, and account_links. It summarizes balances, regions, transfer volumes, merchant concentration, transaction categories, and business impact without using graph-enriched gold tables.
```

Supervisor routing guidance:

- For fraud-ring discovery, call the Neo4j GDS fraud specialist first.
- For business impact on returned account IDs, call BEFORE Genie second.
- For final answers, combine graph evidence with silver-table business context.
- Do not ask BEFORE Genie to discover graph communities on its own.
- Do not cite gold tables or AFTER Genie in the new demo path.

## Demo Prompts

Run these prompts in order:

1. `Using only the Neo4j graph, find likely fraud-ring candidates from GDS evidence. Return compact account IDs and why each group is suspicious.`
2. `For the highest-priority candidate, provide a BEFORE Genie prompt that analyzes the returned account IDs against silver tables.`
3. `Find likely fraud rings, then use silver-table business context to recommend which candidate investigators should prioritize.`

Expected behavior:

- Prompt 1 routes to this graph endpoint and calls Neo4j MCP tools.
- Prompt 2 returns a prompt that the Supervisor Agent can pass to BEFORE Genie.
- Prompt 3 routes to both subagents and produces a synthesized answer.

## Validation

Validation succeeds when:

- MCP tools are discovered through the Databricks external MCP proxy.
- A read-only Cypher query can inspect Account GDS properties.
- The deployed endpoint response contains a tool result.
- The endpoint returns candidate evidence suitable for downstream Genie analysis.
- The combined Supervisor Agent trace shows this endpoint followed by BEFORE
  Genie.

## Completion Criteria

- This directory can deploy the graph-specialist endpoint without AFTER Genie.
- Setup does not require gold tables.
- The endpoint returns graph candidates and evidence from Neo4j.
- The Supervisor Agent uses returned IDs to ask BEFORE Genie for silver-table
  analysis.
