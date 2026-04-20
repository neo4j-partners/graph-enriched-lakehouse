# Graph-Enriched Lakehouse: Finance Genie

## Overview

The Finance Genie demo shows what becomes possible when Neo4j GDS runs as a silver-to-gold enrichment stage inside a Databricks Lakehouse. The pipeline reads relationships from the existing Silver tables, runs three deterministic graph algorithms in Neo4j Aura, and writes three scalar columns (`risk_score`, `community_id`, `similarity_score`) back into the Gold layer. Genie, SQL warehouses, dashboards, and downstream ML read those columns without any interface change.

The demo has a before and an after. The BEFORE space runs against unenriched Silver tables. The first questions are standard BI: account balances, transfer volumes, top merchants. Genie handles them cleanly. The next questions target network structure: which accounts are central hubs, which groups of accounts move money tightly among themselves. Genie answers the question it can answer with the data it has, not the question that was asked. Transfer volume is not network centrality. No amount of SQL over flat rows produces eigenvector centrality. The gap is genuine.

The AFTER space runs against the enriched Gold tables. GDS has already done the structural work. `risk_score` is PageRank eigenvector centrality. `community_id` is a Louvain community partition. `similarity_score` is Jaccard overlap of shared-merchant sets. These are features with published mathematical definitions, not fraud verdicts. The analyst, investigator, or downstream model adjudicates. Genie reads those columns the same way it reads any other column in the catalog and answers a different class of question: portfolio composition by community, cohort comparisons across risk tiers, community rollups, operational workload by region, merchant-side analysis conditioned on structural membership.

The enrichment pipeline is not better algorithms applied to the same data. It converts network topology into columns, making a question class available to Genie that did not exist in the Silver layer.

For guidance on where this enrichment pattern fits in production and how to calibrate it for a customer dataset, see [SCOPING_GUIDE.md](./SCOPING_GUIDE.md).

## workshop/ vs automated/

`workshop/` contains interactive Jupyter notebooks for step-by-step execution by participants on a dedicated Databricks cluster. The notebooks walk through each pipeline stage in sequence and are the primary path for live demo delivery.

`automated/` contains CLI-driven Python scripts that submit the same pipeline logic as unattended Databricks Jobs. The demo owner uses these for one-time setup (data generation, table upload, secret configuration) and for automated validation of Genie Space quality after GDS runs.

---

**Workshop participants:** see [workshop/README.md](./workshop/README.md) for the notebook sequence, cluster prerequisites, and demo guide.

**Demo owner / CI:** see [automated/README.md](./automated/README.md) for data generation, table upload, secret management, the automated validation pipeline, and the CLI command reference.
