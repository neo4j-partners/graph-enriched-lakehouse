## Overview

Agentic Commerce is a retail shopping assistant that runs on Databricks. It combines a Neo4j knowledge graph with Databricks lakehouse tables to answer product questions, remember customer preferences, and make personalized recommendations. The implemented assistant is built as a LangGraph ReAct agent, wrapped in an MLflow ChatAgent, and deployed to a Databricks Model Serving endpoint. A planned Genie lakehouse agent and supervisor will handle analytics queries over Delta Lake tables, while the implemented commerce KG agent handles everything that benefits from graph structure: product search, support diagnostics, and cross-session memory.

Status key:

- **Implemented**: present in the repo and validated against the deployed Agentic Commerce agent endpoint.
- **Planned**: designed or stubbed, but not deployed as working behavior yet.

## The Deployed Agent

The Agentic Commerce agent is a conversational shopping assistant deployed as a single Databricks Model Serving endpoint. It receives chat messages from users, decides which tools to call using a ReAct reasoning loop, and returns natural language responses grounded in data from the Neo4j knowledge graph. It is designed to handle multiple users and sessions concurrently from one endpoint.

**Implemented: what the Agentic Commerce KG agent can do:**

- **Search the product catalog** — find products by description, filter by category, brand, or price, and return structured details including name, price, and attributes
- **Navigate product relationships** — traverse the knowledge graph to find related products by category, brand, shared attributes, or purchase patterns (frequently bought together, similar items)
- **Answer support and troubleshooting questions** — search knowledge articles, support tickets, and reviews using GraphRAG retrieval to surface relevant symptoms, root causes, and documented solutions for product issues
- **Diagnose specific product problems** — given a product and a symptom description, look up known issues and fixes linked to that product in the graph
- **Remember the current conversation** — store messages and automatically extract entities (people, brands, products mentioned) so the agent can refer back to earlier parts of the session
- **Learn user preferences over time** — track brand, category, size, budget, activity, and material preferences tied to a user ID that persist across sessions
- **Give personalized recommendations** — combine a user's stored preference profile with knowledge graph traversal to suggest products tailored to their history and stated needs
- **Learn from past problem-solving** — record how multi-step tasks were handled (which tools were called, what worked) and recall those approaches when facing similar tasks in future sessions
- **Return demo metadata** — preserve normal assistant prose while returning structured live metadata under `ChatAgentResponse.custom_outputs.demo_trace` for product results, related products, knowledge chunks, diagnosis details, profile reads, memory writes, warnings, and tool timeline entries

**Implemented: how it is packaged:**

- The agent is a Python class (`RetailAgent`) that inherits from MLflow's ChatAgent interface
- It is logged to MLflow as a source file using the Models from Code pattern, not as a serialized object
- The `retail_agent` package is bundled alongside it via MLflow `code_paths` so the endpoint has the agent, tools, and integrations at runtime
- Neo4j credentials are injected as Databricks secrets at deploy time and read from environment variables when the endpoint starts
- The endpoint initializes lazily on the first real request after serving-time secrets are available
- The active validated demo endpoint is `agents_retail_assistant-retail-retail_agent_v3`, with model version 15 receiving traffic
- Scale-to-zero is requested by deployment configuration, but the active served endpoint versions currently report `scale_to_zero_enabled: false`

## Key Technologies

- **Databricks Model Serving** — hosts the agent as a serverless endpoint. Scale-to-zero is requested in deployment configuration, but the active served endpoint versions currently report it disabled.
- **MLflow (Models from Code)** — the agent is logged as a Python source file rather than a serialized object, which avoids issues with async resources and gives full control over startup
- **LangGraph** — provides the ReAct agent loop and tool runtime with dependency injection
- **Claude Sonnet 4.6 on Databricks** — the LLM powering the agent, accessed through the Databricks Foundation Model API
- **Neo4j** — stores the product knowledge graph (products, categories, brands, attributes, and their relationships) and the agent memory graph (conversation history, user preferences, reasoning traces). Three Neo4j libraries divide the work:
  - **neo4j Python driver** — async and sync drivers for direct Cypher execution, used for graph queries in the deployed agent and DDL operations during data loading
  - **neo4j-graphrag-python** — handles knowledge graph construction (chunking, embedding, entity extraction) and provides the retriever patterns (VectorCypher, HybridCypher, Text2Cypher) demonstrated in the retriever demo scripts
  - **neo4j-agent-memory** — gives the agent persistent short-term, long-term, and reasoning memory backed by Neo4j, with semantic search over past interactions. The Databricks serving configuration disables conversation entity extraction so it does not need an additional extraction model at runtime.
  - **Neo4j Spark Connector** — two-way bridge between Databricks and Neo4j, used for bulk-loading product nodes and relationships from Spark DataFrames
- **Databricks Delta Lake** — stores transactional and analytical data (1M+ transactions, customers, reviews, inventory). Planned Genie integration will query these tables via natural language to SQL.
- **Databricks BGE Embeddings** — a 1024-dimension embedding model used for vector similarity search across both product descriptions and knowledge articles

## Integration Patterns

- **Implemented and planned dual database architecture** — Neo4j handles relational and semantic queries (product graph, support knowledge, memory) while Delta Lake holds analytical data (sales trends, inventory counts). The two stores share a product ID key so results can be joined across systems.
  - **Planned:** A Databricks supervisor agent will route each question to the right backend: Neo4j for product and support queries, Genie for analytics over Delta Lake
  - Neo4j stores 570+ products with Category, Brand, and Attribute nodes connected by relationships like BOUGHT_TOGETHER and SIMILAR_TO
  - Delta Lake holds 1M+ rows across five tables (transactions, customers, reviews, inventory, stores) with column comments so Genie can generate SQL from natural language
- **GraphRAG retrieval** — knowledge articles, support tickets, and reviews are chunked, embedded, and linked to product nodes in Neo4j. At query time, the agent runs a vector search to find relevant chunks, then traverses graph relationships to surface related products, known symptoms, and solutions. This gives better answers than vector search alone because it follows the structure of the data.
  - Source documents are split into chunks, embedded with Databricks BGE, and stored as Chunk nodes with vector and fulltext indexes
  - An LLM extracts Feature, Symptom, and Solution entities from each chunk and links them back into the graph
  - Three retrieval modes: vector search with entity traversal, hybrid (fulltext + vector) with traversal, and product-scoped symptom/solution lookup
- **Three-layer memory** — short-term memory (scoped to a session) stores the current conversation and embeddings. Long-term memory (scoped to a user) stores preferences like favorite brands and budget ranges. Reasoning memory records past multi-step problem-solving approaches so the agent can reuse successful strategies.
  - Short-term: stores embedded messages scoped to a session ID
  - Long-term: tracks brand, category, budget, activity, and material preferences scoped to a user ID and persisted across sessions
  - Reasoning: records multi-step problem-solving traces with per-step thoughts, tool calls, and outcomes so the agent can recall successful approaches for similar future tasks
- **Neo4j Agent Memory library on Databricks** — shows how to integrate the neo4j-agent-memory Python library into a Databricks Model Serving environment, from initialization through to per-request usage across all three memory layers.
  - The MemoryClient is initialized lazily on first real request with Neo4j credentials pulled from Databricks secrets and a custom DatabricksEmbedder that wraps the Foundation Model API to satisfy the library's Embedder interface
  - Each incoming request constructs a RetailContext with the shared MemoryClient plus the caller's session ID and user ID, and LangGraph injects that context into every tool automatically via ToolRuntime
  - Tools call the MemoryClient directly for short-term operations (store and recall messages), long-term operations (track and retrieve preferences with user ID metadata), and reasoning operations (record and search multi-step traces)
- **Persistent async event loop** — the Neo4j async driver must stay bound to one event loop. The serving adapter creates a background thread with a long-lived loop and dispatches all async work there, avoiding the problems that come with creating and destroying loops per request.
  - A daemon thread runs a single asyncio loop for the lifetime of the serving process
  - The MemoryClient connects on that loop during lazy initialization so the Neo4j driver is bound to the persistent loop from the start
  - Every incoming request dispatches async work to the same loop via run_coroutine_threadsafe

## What This Teaches

- How to deploy a LangGraph agent to Databricks Model Serving using MLflow's Models from Code pattern
- How to use Neo4j as both a domain knowledge graph and an agent memory store in the same application
- How to combine vector search with graph traversal (GraphRAG) to get more relevant retrieval results than either approach alone
- How to plan a multi-agent system where a supervisor routes questions to specialized agents (graph agent vs. SQL agent) based on what each is good at
- How to manage secrets, async resources, and multi-tenant state in a serverless serving environment

## Planned Work

- Implement the Mosaic AI multi-agent supervisor currently stubbed in `retail_agent/agent/supervisor.py`.
- Provision and wire a Genie space for lakehouse analytics over the Delta tables.
- Deploy the supervisor as a separate Model Serving endpoint once the Genie and routing implementation is complete.
- Wire the demo-client frontend submit helper to the implemented backend demo routes. The backend routes exist, but the current frontend still uses local sample demo data.
