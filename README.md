# Graph-Enriched Lakehouse

Graph enrichment connects Neo4j Graph Data Science to a Databricks Lakehouse as a silver-to-gold pipeline stage. The pipeline reads Silver tables from Unity Catalog, loads the records into Neo4j as a property graph, runs graph algorithms against the network, and writes the results back to the Gold layer as plain Delta columns. Genie, SQL warehouses, dashboards, and downstream ML read those columns without modification. The analytics stack stays unchanged. The catalog gains dimensions it could not carry before.

---

## Projects

### [Agentic Commerce](./agentic-commerce/README.md)

A Databricks-hosted agentic commerce example backed by Neo4j. The assistant uses a Neo4j product knowledge graph, GraphRAG retrieval, and graph-backed memory to search products, diagnose issues, remember customer preferences, and personalize recommendations. The project also includes a Databricks App demo client and deployment pipeline for Mosaic AI Model Serving.

Start here:

- [agentic-commerce/README.md](./agentic-commerce/README.md): project overview, setup, deployment, and validation.
- [agentic-commerce/docs/agentic-commerce.md](./agentic-commerce/docs/agentic-commerce.md): design narrative for GraphRAG plus agent memory.
- [agentic-commerce/demo-client/README.md](./agentic-commerce/demo-client/README.md): local and deployed demo client workflow.

### [Finance Genie](./finance-genie/README.md)

A fraud-surfacing demo for Databricks account teams and partners. Financial crime is a network problem: fraud rings operate as connected patterns across many accounts and transactions, and the individual event looks clean while the connected pattern does not. A high-level synthetic fraud dataset loads into Neo4j Aura as a property graph. PageRank, Louvain community detection, and Node Similarity run against the projection and write `risk_score`, `community_id`, and `similarity_score` back to the Gold layer as plain Delta columns: centrality, community membership, and structural similarity materialized where every Databricks tool can reach them.

The demo runs in two phases. The BEFORE space queries unenriched Silver tables: Genie handles standard BI questions cleanly, then falls short on structural-discovery questions because network topology does not exist in flat rows. The AFTER space queries the enriched Gold tables: portfolio composition by risk tier, cohort comparisons across community membership, operational workload estimates, and merchant-side analysis conditioned on structural membership. Questions that require no graph knowledge to read, over a catalog that did not carry those dimensions before the pipeline ran.

Start here:

- [finance-genie/README.md](./finance-genie/README.md): project overview and navigation.
- [finance-genie/ARCHITECTURE.md](./finance-genie/ARCHITECTURE.md): stage-by-stage pipeline reference, signal parameters, and what each GDS algorithm guarantees.
- [finance-genie/SCOPING_GUIDE.md](./finance-genie/SCOPING_GUIDE.md): where the pattern applies, dataset sizing, and production-scale calibration.
- [finance-genie/TALK_TRACK.md](./finance-genie/TALK_TRACK.md): one-slide field script for account teams and partner SEs.
- [finance-genie/automated/README.md](./finance-genie/automated/README.md): CLI-driven job runner, Genie non-determinism discussion, and automated validation.
- [finance-genie/workshop/README.md](./finance-genie/workshop/README.md): notebook sequence for live demo delivery.
