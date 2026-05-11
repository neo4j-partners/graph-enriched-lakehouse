# Agentic Commerce

Agentic Commerce is a Databricks-hosted shopping assistant backed by Neo4j. It can search products, diagnose product issues, answer GraphRAG-backed support questions, remember user preferences, and use those preferences for personalized recommendations.

The deployment path builds a local `retail_agent` wheel, uploads it to a Unity Catalog volume, and submits Databricks Python wheel entry points with `databricks-job-runner`. For design background, see [Agentic Commerce: GraphRAG Meets Agent Memory on Neo4j](docs/agentic-commerce.md). For lower-level GraphRAG notes, see [Developer's Guide: GraphRAG on Databricks](docs/DevelopersGuideGraphRAG-Databricks.md).

## What This Repo Contains

- An MLflow `ChatAgent` model implemented in `retail_agent/agent/serving.py`.
- A LangGraph ReAct agent with product, knowledge, memory, preference, commerce, reasoning, and diagnostic tools.
- Databricks job entry points for product graph loading, GraphRAG loading, model deployment, and endpoint verification.
- Neo4j graph schemas for product relationships, GraphRAG retrieval, and agent memory.
- Lakehouse data generation scripts for optional SQL and Genie-style analytics demos.
- A stub Mosaic AI multi-agent supervisor for future Genie plus KG-agent routing.

## Prerequisites

1. Python 3.12 or newer.
2. `uv` installed locally.
3. Databricks CLI configured with a profile that can access the target workspace.
4. A running Databricks cluster for job steps.
5. Unity Catalog catalog, schema, and volume:
   - `retail_assistant`
   - `retail`
   - `retail_volume`
6. A Neo4j database reachable from Databricks.
7. Databricks model serving access to:
   - `databricks-claude-sonnet-4-6`
   - `databricks-bge-large-en`

The product loader uses Spark and the Neo4j Spark Connector. Use a dedicated-access cluster and install:

```text
org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
```

## Quick Start

Install local dependencies:

```bash
uv sync
```

Create `.env` from `.env.sample` and fill in the Databricks and Neo4j values:

```bash
cp .env.sample .env
```

Upload Neo4j credentials into the Databricks secret scope used by serving:

```bash
./retail_agent/scripts/setup_databricks_secrets.sh --profile <profile>
```

The script reads `NEO4J_URI` and `NEO4J_PASSWORD` from `.env` and writes them to the `retail-agent-secrets` scope. The runner treats these Neo4j values as local setup inputs and does not forward the password as a job parameter.

Validate the Databricks configuration:

```bash
uv run python -m cli validate
```

Run the full pipeline:

```bash
uv run python -m cli pipeline --all
```

Run the demo client locally after the serving endpoint is deployed:

```bash
cd demo-client
cp .env.sample .env
apx dev start
```

Open `http://localhost:9000`. Use `apx dev status`, `apx dev logs`, and `apx dev stop` to manage the local app. See [demo-client/README.md](demo-client/README.md) for full local checks, runtime settings, backend smoke tests, and deployment commands.

## Pipeline

`pipeline` is a local orchestrator over the existing Databricks wheel jobs. It builds and uploads the current wheel, submits each Databricks job in order, waits for each job to finish, and stops on the first failure.

Pipeline modes:

Run the full end-to-end path: upload the wheel, load Neo4j data, build GraphRAG, deploy the endpoint, and run all verification jobs.

```bash
uv run python -m cli pipeline --all
```

Run only the data path: upload the wheel, load products/source knowledge into Neo4j, and build the GraphRAG layer.

```bash
uv run python -m cli pipeline --data
```

Run only deployment: upload the wheel and deploy the agent endpoint. Use this after code changes that do not require reloading Neo4j data.

```bash
uv run python -m cli pipeline --deploy
```

Run only verification against an existing deployed endpoint.

```bash
uv run python -m cli pipeline --verify
```

Pipeline steps:

| Step | What it does | Individual command |
|------|--------------|--------------------|
| Upload wheel | Builds `retail_agent` and uploads it to `DATABRICKS_VOLUME_PATH/wheels` | `uv run python -m cli upload --wheel` |
| Load products | Creates the retail product graph, source knowledge nodes, product embeddings, and memory indexes in Neo4j | `uv run python -m cli submit retail-agent-load-products` |
| Build GraphRAG | Reads source knowledge from Neo4j, runs `SimpleKGPipeline`, creates chunks/entities, links them to products, and creates retrieval indexes | `uv run python -m cli submit retail-agent-load-graphrag` |
| Deploy agent | Logs the agent to MLflow, registers `retail_assistant.retail.retail_agent_v3`, deploys with `databricks-agents`, and waits for active traffic | `uv run python -m cli submit retail-agent-deploy` |
| Verify endpoint | Checks endpoint readiness, diagnostics, product tools, short-term memory, and long-term preferences | `uv run python -m cli submit retail-agent-demo` |
| Verify retrievers | Demonstrates vector, vector-plus-Cypher, hybrid, and Text2Cypher GraphRAG retrievers | `uv run python -m cli submit retail-agent-demo-retrievers` |
| Verify knowledge | Sends live troubleshooting, hybrid search, issue diagnosis, and comparison queries through the endpoint | `uv run python -m cli submit retail-agent-check-knowledge` |

Useful options:

```bash
uv run python -m cli pipeline --all --dry-run
uv run python -m cli pipeline --data --skip-upload
uv run python -m cli pipeline --verify --compute serverless
```

Use `uv run python -m cli logs <run-id>` after a submitted step to inspect Databricks task output.

## Focused Testing

Test only the deployed agent endpoint on Databricks:

```bash
uv run python -m cli submit retail-agent-demo
uv run python -m cli submit retail-agent-check-knowledge
uv run python -m cli logs <run-id>
```

`retail-agent-demo` verifies endpoint readiness, diagnostics, product search,
product lookup, graph traversal, short-term memory, long-term preferences,
profile retrieval, and preference-based recommendations.

`retail-agent-check-knowledge` verifies the GraphRAG path with knowledge search,
hybrid search, product diagnosis, and cross-product knowledge comparison.

Test only the local `retail_agent` package before submitting Databricks jobs:

```bash
uv run python -m pytest tests
uv run python -m compileall retail_agent
uv run python -m cli validate retail-agent-demo
```

## Individual Commands

The single pipeline command is the normal path. Use these commands for debugging or rerunning one step.

```bash
# Show project CLI help
uv run python -m cli --help

# Validate cluster access and available wheel entry points
uv run python -m cli validate

# Build and upload the package wheel
uv run python -m cli upload --wheel

# Run one wheel entry point
uv run python -m cli submit retail-agent-demo

# View Databricks job logs
uv run python -m cli logs <run-id>
```

Available wheel entry points:

| Entry point | Purpose |
|-------------|---------|
| `retail-agent-load-products` | Load product catalog, source knowledge, relationships, product embeddings, and memory indexes |
| `retail-agent-load-graphrag` | Build the GraphRAG chunk/entity layer and retrieval indexes |
| `retail-agent-deploy` | Log, register, deploy, and wait for the serving endpoint |
| `retail-agent-demo` | Verify endpoint, product tools, and memory |
| `retail-agent-demo-retrievers` | Demonstrate GraphRAG retriever patterns |
| `retail-agent-check-knowledge` | Verify knowledge tools through the live endpoint |
| `retail-agent-deploy-supervisor` | Stub supervisor deployment entry point |

## Local Validation

Run local checks before submitting Databricks jobs:

```bash
uv run python -m pytest
uv run python -m compileall -q retail_agent demo-client/src
uv run python -m cli validate
```

The latest verified Databricks pipeline completed product loading, GraphRAG loading, endpoint deployment, endpoint and memory checks, retriever demos, and knowledge checks successfully. The verified endpoint was `agents_retail_assistant-retail-retail_agent_v3`.

## Optional Lakehouse Data

The main agent runtime uses Neo4j. The repo also contains scripts for generating synthetic retail lakehouse data for Databricks SQL and Genie-style analytics demos.

This step is optional for the current Agentic Commerce pipeline. If you do not generate or upload the lakehouse data, the Neo4j-backed product search, GraphRAG tools, memory, recommendations, model deployment, and endpoint checks still work. What you do not get is the separate Delta table dataset used for SQL analytics or future Genie/supervisor demos.

Generate expanded catalog data:

```bash
uv run python -m retail_agent.scripts.generate_transactions --expanded --verify
```

This writes CSVs to `data/lakehouse/`:

| File | Rows | Description |
|------|------|-------------|
| `transactions.csv` | ~1.15M | Line items across 500K orders |
| `customers.csv` | 5,000 | Customer dimension with segments |
| `reviews.csv` | ~115K | Product reviews linked to transactions |
| `inventory_snapshots.csv` | ~417K | Daily stock levels per product |
| `stores.csv` | 20 | Physical store locations |
| `knowledge_articles.csv` | Product knowledge articles | Product manuals, FAQs, and troubleshooting content |

Upload CSVs and create Delta tables:

```bash
uv run python -m retail_agent.scripts.lakehouse_tables
```

Options:

```bash
uv run python -m retail_agent.scripts.lakehouse_tables --skip-upload
uv run python -m retail_agent.scripts.lakehouse_tables --skip-tables
```

## Architecture

```text
+------------------------+
| Developer machine      |
| uv + .env + CLI        |
+-----------+------------+
            |
            | build and upload retail_agent wheel
            v
+------------------------+          +-----------------------------+
| Unity Catalog Volume   |          | Databricks Workspace        |
| wheels/retail_agent    |          | one-time wheel job submits  |
+-----------+------------+          +--------------+--------------+
            |                                      |
            | wheel dependency                     | submit tasks
            v                                      v
+---------------------------------------------------------------+
| Databricks Job Cluster                                        |
| 1. load product graph and source knowledge into Neo4j          |
| 2. build GraphRAG chunks, entities, relationships, indexes     |
| 3. log/register/deploy the agent model                         |
| 4. run endpoint, retriever, and knowledge verification         |
+----------------------------+----------------------------------+
                             |
                             | deploys and verifies
                             v
+---------------------------------------------------------------+
| Databricks Model Serving                                      |
| MLflow ChatAgent + LangGraph ReAct agent + ChatDatabricks LLM |
+----------------------------+----------------------------------+
                             |
                             | reads and writes
                             v
+---------------------------------------------------------------+
| Neo4j                                                         |
| Product graph + GraphRAG retrieval graph + agent memory       |
+---------------------------------------------------------------+

Optional analytics path:

+------------------------+          +-----------------------------+
| Lakehouse generator    |          | Delta tables / SQL / Genie  |
| synthetic retail CSVs  +--------->| analytics demos             |
+------------------------+          +-----------------------------+
```

### Agent Tools

| Tool group | Purpose |
|------------|---------|
| Product tools | Product search, product details, related products |
| Knowledge tools | GraphRAG semantic search, hybrid keyword/vector search, product issue diagnosis |
| Memory tools | Session-scoped remember, recall, and semantic memory search |
| Preference tools | User-scoped long-term preference tracking and profile retrieval |
| Commerce tools | Preference-aware product recommendations using knowledge graph traversal |
| Reasoning tools | Store and recall multi-step reasoning traces |
| Diagnostics | Validate serving-time tool injection and Neo4j/memory initialization |

### Data Layers

| Layer | Main nodes and relationships | Built by |
|-------|------------------------------|----------|
| Product graph | `Product`, `Category`, `Brand`, `Attribute`; `IN_CATEGORY`, `MADE_BY`, `HAS_ATTRIBUTE`, `SIMILAR_TO`, `BOUGHT_TOGETHER` | `retail-agent-load-products` |
| Source knowledge | `KnowledgeArticle`, `SupportTicket`, `Review`; source document relationships to products | `retail-agent-load-products` |
| GraphRAG layer | `Document`, `Chunk`, `Feature`, `Symptom`, `Solution`; retrieval and product shortcut relationships | `retail-agent-load-graphrag` |
| Agent memory | `Message`, `Preference`, `Fact`, `Task` and memory vector indexes | `neo4j-agent-memory` at serving time |
| Lakehouse analytics | Generated retail CSVs uploaded as Delta tables for SQL and Genie demos | `retail_agent.scripts.generate_transactions`, `retail_agent.scripts.lakehouse_tables` |

Databricks provides the job execution environment, MLflow model registry, Model Serving endpoint, LLM endpoint, embedding endpoint, Unity Catalog volume for wheels, and optional Delta Lake tables for analytics demos.

## Supervisor Stub

The repository is structured for a future Mosaic AI multi-agent supervisor that routes analytics questions to a Genie space and product/KG questions to the deployed retail KG agent endpoint. The implementation is currently a stub:

- `retail_agent/agent/supervisor.py` contains sub-agent specs, `build_supervisor_chat_agent()` that raises `NotImplementedError`, and the TODO list in the module docstring.
- `retail_agent/deployment/deploy_supervisor.py` prints a `STUB` banner and exits nonzero.
- `retail-agent-deploy-supervisor` is the wheel entry point for the current supervisor stub.
- `retail_agent/agent/config.py` includes `supervisor_model_name` and `genie_space_id`; `genie_space_id` is empty by default and must be set before any real deployment.

To make this real, provision the Genie space, replace the supervisor skeleton with a `databricks_ai_bridge.GenieAgent` plus multi-agent supervisor implementation, mirror `deploy_agent.py` in `deploy_supervisor.py`, and add a check script.

## Project Structure

```text
cli/
`-- __main__.py                       # project CLI entry point

retail_agent/
|-- agent/                            # ChatAgent adapter, LangGraph agent, config, supervisor stub
|-- tools/                            # catalog, knowledge, memory, preferences, reasoning, commerce, diagnostics
|-- integrations/                     # Databricks and Neo4j integration helpers
|-- deployment/                       # Databricks wheel entry points
|-- demos/                            # endpoint and retriever checks
|-- data/                             # product catalog and source knowledge fixtures
`-- scripts/                          # lakehouse generation and secret setup helpers

demo-client/                          # optional frontend/backend demo client
docs/                                 # architecture and implementation notes
tests/                                # local tests
```
