# SCOPING_GUIDE: Where this enrichment pattern applies and how to calibrate it

This guide is written for Databricks account teams and partner SEs to forward to customers ahead of a scoping conversation. Its purpose is to set calibrated expectations about what the Finance Genie pipeline produces, where the pattern fits well, and what adjustments to plan for at production scale.

## What this pattern produces

Neo4j GDS runs as a silver-to-gold enrichment stage inside the Databricks Lakehouse. It reads relationships from the existing silver tables, runs three deterministic graph algorithms against a projection in Neo4j Aura, and writes three scalar columns back into the gold layer:

- `risk_score` (float): eigenvector centrality from PageRank
- `community_id` (integer): modularity-optimal community assignment from Louvain
- `similarity_score` (float): Jaccard overlap of shared-merchant sets from Node Similarity

Every tool that reads a Delta table reads these columns. Genie generates SQL against them, SQL warehouses query them, dashboards render them, and downstream ML consumes them as features. No new query interface, no new data type, no new tool for the analyst to learn.

## Where it applies well

The pattern fits any workload where the answer lives in relationships rather than individual rows. Representative use cases:

- **Fraud-ring surfacing.** Accounts transacting within a tight community, or sharing merchant preferences that do not fit the background distribution.
- **Entity resolution.** Collapsing customer, device, and household records that refer to the same real-world entity based on shared attributes and interaction topology.
- **Supplier-network risk.** Identifying tiers of supplier exposure, single points of failure, and concentrations of risk in multi-tier supply graphs.
- **Recommendation structure.** Surfacing communities of users, products, or content with shared consumption patterns as features for downstream recommenders.
- **Compliance network review.** Finding counterparty clusters and beneficial-ownership paths that require human review under regulatory frameworks.

Each is a workload where row-level aggregation reaches its natural limit and a relationship-aware primitive turns the unanswerable into a scalar column the existing lakehouse tools already know how to query.

## Dataset size and calibration

The live workshop dataset uses 25,000 accounts with 4% ring membership. Those parameters are chosen to produce an observable signal inside a 20-minute demo window. The pipeline shape is unchanged at production scale: the projection definition, the algorithm configuration, and the gold-table DDL are identical at 25,000 accounts and at 10,000,000. Two things are reviewed per dataset:

1. The signal parameters inside the data generator (for synthetic workloads) or the projection query (for real customer data). The algorithms read whatever the projection presents; the projection is the single place the dataset's structure gets expressed to GDS.
2. The verification thresholds in `validation/verify_gds.py`. These are sanity checks calibrated to the demo dataset. For a production dataset, the thresholds become acceptance criteria set against the customer's observed base rates.

The signal ratios the algorithms detect (within-ring density relative to background, fraud-to-normal Jaccard ratio, PageRank separation) are theoretically invariant to base rate when ring mechanics scale proportionally. An empirical verification of that claim at one million accounts and 0.1% ring membership is published under `scale_companion/` when available.

## What to plan for at production scale

- **Aura sizing.** A larger Aura instance covers the GDS stage. GDS memory scales with projected node and edge count rather than with the full silver population, so the sizing conversation starts from the projection, not the raw tables.
- **Candidate triage capacity.** A production base rate produces a longer candidate list than the 10-ring demo output. Investigator headcount, a supervised classifier trained on the gold columns, or a rules layer downstream of the gold tables consumes that list.
- **Base-rate-aware thresholds.** The `fraud_risk_tier` column in this demo is binary and keyed to the demo's base rate. At production base rates, the tier logic, or an equivalent column, is recalibrated against the customer's observed distribution.
- **Databricks-side scaling.** The ingest job, gold production, validation gate, Genie Space, and dashboards run on the same warehouse and cluster configuration the customer already operates. The enrichment adds a Neo4j Aura instance and a silver-to-gold job; it does not change the existing lakehouse footprint.

Same Databricks spend. Strictly more answers.
