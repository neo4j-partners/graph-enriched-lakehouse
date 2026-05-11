# Rules

- Always ask clarifying questions before making changes. Do not assume intent, scope, or approach — confirm with the user first.

# Agentic Commerce Project

## Directory Structure

- `retail_agent/` — **Databricks-only** agent package. Uses `ToolRuntime[RetailContext]` dependency injection instead of closures. Deployed to Databricks Model Serving via MLflow and `agents.deploy()`. This code runs on Databricks, not locally.

## retail_agent/ — Databricks Agent

This package is designed to run on Databricks Model Serving. Implementation code is organized by responsibility and Databricks jobs run Python wheel entry points directly.

### Layout

- `agent/` — Core agent runtime:
  - `serving.py` — MLflow ChatAgent adapter
  - `graph.py` — LangGraph ReAct agent definition
  - `config.py` — Deployment configuration (CONFIG singleton)
  - `context.py` — RetailContext dataclass for DI
- `tools/` — Agent tools grouped by domain:
  - `catalog.py` — Product search/lookup/related tools
  - `knowledge.py` — GraphRAG search and diagnosis tools
  - `memory.py` — Memory tools (remember, recall, search)
  - `preferences.py` — Long-term preference tools
  - `reasoning.py` — Reasoning trace tools
  - `commerce.py` — Personalized recommendation tools
  - `diagnostics.py` — Agent environment diagnostics
- `integrations/` — Databricks and Neo4j helper modules:
  - `databricks/embeddings.py` — Foundation Model embedder
  - `databricks/graphrag.py` — neo4j-graphrag Databricks adapters
  - `databricks/endpoint_client.py` — Model Serving endpoint client
  - `neo4j/memory_helpers.py` — Neo4j memory helper functions
- `deployment/` and `demos/` — Databricks wheel entry point implementations
- `data/` — Product data definitions:
  - `product_catalog.py` — Product data definitions
  - `product_knowledge.py` — Knowledge articles, support tickets, reviews
- `scripts/` — Databricks data pipeline scripts:
  - `generate_transactions.py` — Generate 500K transaction CSVs for Delta Lake
  - `lakehouse_tables.py` — Upload CSVs to Databricks Unity Catalog

### Key constraints

- **No `test_` prefixed files** — Databricks auto-discovers and runs them as pytest. Use names like `check_endpoint.py` instead.
- **Package imports** — Runtime modules use package-qualified imports under `retail_agent.*`; MLflow packages the `retail_agent` package via `code_paths`.
- **Async bridging** — Uses a persistent background event loop, never `asyncio.run()`.
- **Deploy**: Submit `retail-agent-deploy` with the CLI
- **Check**: Submit `retail-agent-demo` with the CLI

## Running Scripts

Wheel entry points run on Databricks via `uv run python -m cli submit <entry-point>`:

- `retail-agent-check-knowledge` — Exercise GraphRAG knowledge tools

Local data pipeline scripts (run with `uv run`):

```
uv run python -m retail_agent.scripts.generate_transactions
uv run python -m retail_agent.scripts.lakehouse_tables
```
