# Graph-Enriched Lakehouse: Finance Genie

[Project website and slides](https://neo4j-partners.github.io/graph-enriched-lakehouse/)

## Quick Start: Shared Environment

All Finance Genie subprojects now use a shared environment file at the repo
root. Create it once, then reuse it for `automated/`, `analyst-client/`,
`finance-client/`, `neo4j-mcp-demo/`, `multi-agent-demo/`, and `apx-demo/`.

```bash
cd finance-genie
cp .env.sample .env
# Edit .env and fill in Databricks, Neo4j, Genie, and MCP values.
```

Provision Databricks secrets from the same root env file:

```bash
./setup_secrets.sh --profile <databricks-profile>
```

The root setup writes separate Databricks secret scopes for separate runtime
surfaces. This keeps one operator workflow without giving every app access to
every secret:

| Scope | Used by | Contents |
|---|---|---|
| `neo4j-graph-engineering` | `automated/` jobs and workshop notebooks | Neo4j URI, username, password, before/after Genie Space IDs |
| `finance-genie-analyst-client` | `analyst-client` real backend | Neo4j URI, username, password, analyst Genie Space ID |
| `mcp-neo4j-secrets` | `neo4j-mcp-demo` and MCP-backed agents | AgentCore OAuth gateway/client credentials, when `.mcp-credentials.json` is available |

Existing per-project `.env` files remain fallback-only for compatibility. New
setup should use `finance-genie/.env`.

## Graph-Enriched Lakehouse Path

This is the original before/after demo path. Neo4j GDS runs as a silver-to-gold enrichment stage, and Databricks Genie queries graph-derived features after they have been materialized as ordinary Gold Delta columns.

```text
                     finance-genie/automated
                  setup, jobs, validation, CI
                              |
                              v
+--------------------------------------------------------------------+
| Databricks Unity Catalog                                           |
| Silver tables: accounts, merchants, transactions, account_links,   |
| account_labels                                                     |
+-------------------------------+------------------------------------+
                                |
                                | Neo4j Spark Connector
                                v
+--------------------------------------------------------------------+
| Neo4j Aura                                                         |
| Property graph + GDS                                               |
| PageRank -> risk_score                                             |
| Louvain -> community_id                                            |
| Node Similarity -> similarity_score                                |
+-------------------------------+------------------------------------+
                                |
                                | pull enriched results
                                v
+--------------------------------------------------------------------+
| Databricks Unity Catalog                                           |
| Gold tables: gold_accounts, gold_account_similarity_pairs,         |
| gold_fraud_ring_communities                                        |
+-------------------------------+------------------------------------+
                                |
                                v
+--------------------------------------------------------------------+
| AFTER Genie Space, dashboards, SQL, ML                             |
| Queries graph-derived columns like normal warehouse fields          |
+--------------------------------------------------------------------+

Participant path: finance-genie/workshop
Presenter path:   finance-genie/demo-guide
```

Use this path when the point is to show that graph structure can become reusable Databricks data products. The graph evidence enters Databricks as stable Gold columns that any downstream Databricks workflow can consume without calling Neo4j at query time.

## MCP and Supervisor Agent Path

This is the live graph-evidence path. Neo4j GDS still computes the structural evidence, but the evidence is retrieved through MCP by a graph specialist agent and handed to a Databricks Supervisor Agent, which then uses the BEFORE Genie Space for Silver-table business analysis.

```text
+--------------------------------------------------------------------+
| Analyst question                                                   |
+-------------------------------+------------------------------------+
                                |
                                v
+--------------------------------------------------------------------+
| Databricks Supervisor Agent                                        |
| Routes graph discovery first, business impact second               |
+---------------+------------------------------------+---------------+
                |                                    |
                | graph candidate retrieval          | silver-table analysis
                v                                    v
+------------------------------------+   +----------------------------+
| Graph specialist endpoint          |   | BEFORE Genie Space          |
| finance-genie/multi-agent-demo     |   | Silver/base Delta tables    |
| No Genie calls, no Gold dependency |   | accounts, merchants,        |
+---------------+--------------------+   | transactions, account_links |
                |                        +--------------+-------------+
                | Databricks MCP proxy                  |
                v                                       |
+------------------------------------+                  |
| UC HTTP connection with MCP enabled|                  |
| finance-genie/neo4j-mcp-demo       |                  |
+---------------+--------------------+                  |
                |                                       |
                | AgentCore gateway / Neo4j MCP         |
                v                                       |
+------------------------------------+                  |
| Neo4j Aura + GDS evidence          |                  |
| fraud-ring candidates, graph       |                  |
| rationale, account IDs             |                  |
+---------------+--------------------+                  |
                |                                       |
                +-------------------+-------------------+
                                    v
+--------------------------------------------------------------------+
| Supervisor synthesis                                               |
| Combines graph rationale with Silver-table business context         |
+--------------------------------------------------------------------+
```

Use this path when the point is to show agentic orchestration across live graph tools and Genie. The investigation can reach the same kind of business conclusion without persisting graph-enriched Gold tables.

## Overview

The Finance Genie demo shows what becomes possible when Neo4j GDS runs as a silver-to-gold enrichment stage inside a Databricks Lakehouse. The pipeline reads relationships from the existing Silver tables, runs three deterministic graph algorithms in Neo4j Aura, and writes three scalar columns (`risk_score`, `community_id`, `similarity_score`) back into the Gold layer. Genie, SQL warehouses, dashboards, and downstream ML read those columns without any interface change.

The demo has a before and an after. The BEFORE space runs against unenriched Silver tables. The first questions are standard BI: account balances, transfer volumes, top merchants. Genie handles them cleanly. The next questions target network structure: which accounts are central hubs, which groups of accounts move money tightly among themselves. Genie answers the question it can answer with the data it has, not the question that was asked. Transfer volume is not network centrality. No amount of SQL over flat rows produces eigenvector centrality. The gap is genuine.

The AFTER space runs against the enriched Gold tables. GDS has already done the structural work. `risk_score` is PageRank eigenvector centrality. `community_id` is a Louvain community partition. `similarity_score` is Jaccard overlap of shared-merchant sets. These are features with published mathematical definitions, not fraud verdicts. The analyst, investigator, or downstream model adjudicates. Genie reads those columns the same way it reads any other column in the catalog and answers a different class of question: portfolio composition by community, cohort comparisons across risk tiers, community rollups, operational workload by region, merchant-side analysis conditioned on structural membership.

The enrichment pipeline is not better algorithms applied to the same data. It converts network topology into columns, making a question class available to Genie that did not exist in the Silver layer.

For guidance on where this enrichment pattern fits in production and how to calibrate it for a customer dataset, see [SCOPING_GUIDE.md](./SCOPING_GUIDE.md).

## Project Map

Finance Genie now contains several related but separate projects. They share the same core claim: relationship structure belongs in the Databricks analytical workflow, either as graph-enriched Gold columns or as live graph evidence routed through an agent.

### `demo-guide/`

`demo-guide/` is the narrative and presenter collateral for the graph-enriched lakehouse story. It explains the before/after Genie framing, the GDS enrichment pattern, recommended questions, speaker notes, and slide material. It is not the executable workshop. Treat it as the story source for preparing and delivering the demo.

Start here when you need the positioning, talk track, customer objections, or slide flow.

### `automated/`

`automated/` is the admin and CI-oriented implementation of the original graph-enriched Gold-table pipeline. It generates the synthetic finance dataset, uploads base tables to Unity Catalog, configures secrets, provisions Genie Spaces, submits Databricks Jobs, runs Neo4j ingest and GDS, pulls enriched results back into Gold tables, and validates the output.

Use this before a workshop or live demo to prepare the shared environment. It is also the repeatable path for unattended setup and regression checks.

### `workshop/`

`workshop/` is the participant-facing notebook experience. It walks through the same graph-enrichment idea interactively: query the Silver-only Genie baseline, load Silver tables into Neo4j, run GDS, pull enriched Gold tables back into Databricks, and query the enriched result.

The workshop is separate from `demo-guide/`. The guide is narrative collateral; the workshop is hands-on execution. They should stay aligned, but they serve different audiences and should not be treated as the same artifact.

### `neo4j-mcp-demo/`

`neo4j-mcp-demo/` builds the external MCP integration path. It configures AgentCore OAuth credentials, creates the Databricks Unity Catalog HTTP connection with MCP enabled, validates MCP tool discovery, registers a LangGraph agent, and deploys a Databricks Model Serving endpoint that can call Neo4j MCP tools through the Databricks MCP proxy.

Use this when the demo needs live graph access through MCP rather than only precomputed Gold columns.

### `multi-agent-demo/`

`multi-agent-demo/` contains the Neo4j GDS fraud specialist used by the Databricks Supervisor Agent demo. The specialist is graph-only: it calls Neo4j through the Unity Catalog external MCP proxy and returns compact fraud-ring candidates with graph rationale. It does not query Genie directly and does not depend on the graph-enriched Gold tables.

Use this with a Supervisor Agent that routes first to the graph specialist, then to the BEFORE Genie Space for business impact analysis over the Silver/base tables.

**Presenter prep:** see [demo-guide/prep-guide.md](./demo-guide/prep-guide.md) for the story, questions, and slides.

**Workshop participants:** see [workshop/README.md](./workshop/README.md) for the notebook sequence and cluster prerequisites.

**Demo owner / CI:** see [automated/README.md](./automated/README.md) for data generation, table upload, secret management, automated validation, and CLI commands.

**MCP setup:** see [neo4j-mcp-demo/README.md](./neo4j-mcp-demo/README.md) for Databricks external MCP connection setup and validation.

**Supervisor Agent demo:** see [multi-agent-demo/README.md](./multi-agent-demo/README.md) for the graph specialist endpoint and handoff guidance.

## Slides

- [Full Finance Genie deck](https://neo4j-partners.github.io/graph-enriched-lakehouse/slides.html)
- [15-minute Finance Genie deck](https://neo4j-partners.github.io/graph-enriched-lakehouse/slides-15min.html)
