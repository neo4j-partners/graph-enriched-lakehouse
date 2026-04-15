# Graph-Enriched Lakehouse

Demos that show what happens when Databricks and Neo4j GDS work together — loading Delta tables into a property graph, running graph algorithms, writing the results back as new columns, and letting downstream tools (Genie, ML models) use structural features that no column-based query can produce on its own.

---

## Projects

### [Finance Genie](./finance-genie/README.md)

A fraud-investigation demo that exposes three structural gaps between Genie's column-based analysis and graph algorithm output. A synthetic dataset of 25,000 accounts, 2,500 merchants, and 250,000 transactions is loaded into Neo4j Aura. PageRank, Louvain community detection, and Node Similarity run as GDS algorithms and write `risk_score`, `community_id`, and `similarity_score` back to the lakehouse. Genie then answers the same fraud queries it could not answer against the raw tables.
