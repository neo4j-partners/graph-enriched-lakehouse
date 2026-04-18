# Graph-Enriched Lakehouse: Finance Genie

## Overview

Databricks Genie answers SQL-expressible questions against Delta tables: total transaction volume, merchant revenue, account activity over time. It cannot answer structural questions about which accounts form a fraud ring, which account sits at the center of money flow, or which accounts share the same behavioral fingerprint. Those answers are not properties of individual rows. They are properties of the network connecting them.

This project implements a Tier 1 graph enrichment pipeline that bridges that gap. The pipeline reads account, merchant, and transaction records from Databricks Silver tables, loads them into Neo4j, runs three GDS algorithms (PageRank for centrality, Louvain for community detection, Node Similarity for structural fingerprinting), and writes the results back to Databricks Gold tables as plain numeric columns. Genie queries those columns: `risk_score`, `community_id`, and `similarity_score`. It treats them as ordinary features with no knowledge of the graph computation behind them.

The demo shows the gap before GDS enrichment and closes it after: Genie cannot identify fraud rings or transfer-network hubs against the raw base tables, and can after the pipeline runs.

## workshop/ vs automated/

`workshop/` contains interactive Jupyter notebooks for step-by-step execution by participants on a dedicated Databricks cluster. The notebooks walk through each pipeline stage in sequence and are the primary path for live demo delivery.

`automated/` contains CLI-driven Python scripts that submit the same pipeline logic as unattended Databricks Jobs. The demo owner uses these for one-time setup (data generation, table upload, secret configuration) and for automated validation of Genie Space quality after GDS runs.

---

**Workshop participants:** see [workshop/README.md](./workshop/README.md) for the notebook sequence, cluster prerequisites, and demo guide.

**Demo owner / CI:** see [automated/README.md](./automated/README.md) for data generation, table upload, secret management, the automated validation pipeline, and the CLI command reference.
