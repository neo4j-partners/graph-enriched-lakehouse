# Presenter Script

## Opening

Finance Genie can summarize the silver transaction tables with Genie, but fraud
rings are graph patterns. This demo shows an alternative to copying Neo4j GDS
findings back into gold Delta tables: the Supervisor Agent asks Neo4j for graph
candidates, then asks BEFORE Genie to explain the business impact from silver
data.

## Step 1 - Baseline The Silver-Only Limitation

Prompt for BEFORE Genie:

```text
Find groups of accounts transferring money heavily among themselves.
```

Talk track:

- BEFORE Genie has only row-level silver tables.
- It may return plausible transfer summaries, but it does not have community,
  centrality, or similarity outputs.
- This sets up why the supervisor needs the graph specialist.

## Step 2 - Retrieve GDS Candidates From Neo4j

Prompt for the graph specialist:

```text
Using only the Neo4j graph, find likely fraud-ring candidates from GDS evidence. Return compact account IDs and why each group is suspicious.
```

Talk track:

- The graph specialist routes to Neo4j MCP.
- The response should show GDS-backed evidence such as community, risk score,
  similarity, transfer structure, or shared merchant signal.
- The result should be compact enough to pass to Genie.

## Step 3 - Analyze Candidate IDs With BEFORE Genie

Prompt for the Supervisor Agent:

```text
Use the top fraud-ring candidate from Neo4j and ask BEFORE Genie to summarize those account IDs by region, balances, transfer volume, merchant concentration, and transaction categories.
```

Talk track:

- The Supervisor passes graph candidate IDs into BEFORE Genie.
- Genie uses only silver/base tables for business context.
- The answer connects graph suspicion to operational impact without gold tables.

## Step 4 - Prove The Full Multi-Agent Flow

Prompt for the Supervisor Agent:

```text
Find likely fraud rings, then use silver-table business context to recommend which candidate investigators should prioritize.
```

Talk track:

- The supervisor should call the graph specialist first.
- The supervisor should call BEFORE Genie second with the selected account IDs.
- The final answer should include both graph evidence and business impact.

## Close

The important point is that GDS findings do not need to be materialized into
gold tables for the analyst workflow. Neo4j remains the graph analytics system,
Databricks governs MCP access, and Genie still explains the business context
from governed silver tables.
