# Graph-Enriched Lakehouse

Demos that show what Neo4j GDS adds to a Databricks Lakehouse when it runs as a silver-to-gold enrichment stage. Relationships flow out of the silver tables into a property graph, deterministic graph algorithms run in Neo4j Aura, and the results land back in the gold layer as scalar Delta columns. Every Databricks tool (Genie, SQL warehouses, dashboards, downstream ML) reads those columns without any interface change. Same Databricks spend. Strictly more answers.

---

## Projects

### [Finance Genie](./finance-genie/README.md)

A fraud-surfacing demo for Databricks account teams and partners. A synthetic dataset of 25,000 accounts, 7,500 merchants, 250,000 account-to-merchant transactions, and 300,000 peer-to-peer transfers loads into Neo4j Aura. PageRank, Louvain community detection, and Node Similarity run against the projection and write `risk_score`, `community_id`, and `similarity_score` back into three gold Delta tables. GDS handles the structural analysis: identifying which accounts are central in the transfer network, which form tight communities, which share merchant histories. Genie then answers segment questions over those dimensions: portfolio composition by risk tier, cohort comparisons across community membership, operational workload estimates, and merchant-side analysis conditioned on structural membership. Questions that require no graph knowledge to read, over a catalog that did not carry those dimensions before the pipeline ran.

Start here:

- [finance-genie/README.md](./finance-genie/README.md): project overview and navigation.
- [finance-genie/ARCHITECTURE.md](./finance-genie/ARCHITECTURE.md): stage-by-stage pipeline reference, signal parameters, and what each GDS algorithm guarantees.
- [finance-genie/SCOPING_GUIDE.md](./finance-genie/SCOPING_GUIDE.md): where the pattern applies, dataset sizing, and production-scale calibration.
- [finance-genie/TALK_TRACK.md](./finance-genie/TALK_TRACK.md): one-slide field script for account teams and partner SEs.
- [finance-genie/automated/README.md](./finance-genie/automated/README.md): CLI-driven job runner, Genie non-determinism discussion, and automated validation.
- [finance-genie/workshop/README.md](./finance-genie/workshop/README.md): notebook sequence for live demo delivery.
