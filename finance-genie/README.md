# Graph-Enriched Lakehouse: Finance Genie

## Overview

The Finance Genie demo shows what becomes possible when Neo4j GDS runs as a silver-to-gold enrichment stage inside a Databricks Lakehouse. The pipeline reads relationships from the existing silver tables, runs three deterministic graph algorithms in Neo4j Aura, and writes three scalar columns (`risk_score`, `community_id`, `similarity_score`) back into the gold layer. Genie, SQL warehouses, dashboards, and downstream ML read those columns without any interface change. The fraud use case is one instance of a broader pattern that applies any time the answer lives in relationships rather than individual rows.

For guidance on where this enrichment pattern fits in production and how to calibrate it for a customer dataset, see [SCOPING_GUIDE.md](./SCOPING_GUIDE.md).

## workshop/ vs automated/

`workshop/` contains interactive Jupyter notebooks for step-by-step execution by participants on a dedicated Databricks cluster. The notebooks walk through each pipeline stage in sequence and are the primary path for live demo delivery.

`automated/` contains CLI-driven Python scripts that submit the same pipeline logic as unattended Databricks Jobs. The demo owner uses these for one-time setup (data generation, table upload, secret configuration) and for automated validation of Genie Space quality after GDS runs.

---

**Workshop participants:** see [workshop/README.md](./workshop/README.md) for the notebook sequence, cluster prerequisites, and demo guide.

**Demo owner / CI:** see [automated/README.md](./automated/README.md) for data generation, table upload, secret management, the automated validation pipeline, and the CLI command reference.
