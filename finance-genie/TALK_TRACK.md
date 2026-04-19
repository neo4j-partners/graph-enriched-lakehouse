# TALK_TRACK: Finance Genie field script

One slide of bullet points. Account teams and partner SEs read this off the slide. Pair with a live run of the BEFORE and AFTER Genie Spaces during the middle beat.

## Open: GDS fits naturally as a silver-to-gold enrichment stage

- The Databricks Lakehouse already runs medallion architecture, feature stores, and silver-to-gold transforms. GDS is another transform in that sequence.
- Its input is relationships from the silver tables. Its output is three scalar columns (`risk_score`, `community_id`, `similarity_score`) in the gold layer.
- The fraud use case is one instance. The same pattern covers entity resolution, supplier-network risk, recommendation structure, and compliance review.

## Middle: the deterministic handoff strengthens Genie's answers

- GDS algorithms have published convergence properties. PageRank converges to eigenvector centrality. Louvain converges to a modularity-optimal partition. Node Similarity computes exact Jaccard overlap.
- Those outputs are reproducible given a fixed projection. Placing deterministic compute upstream of Genie's non-deterministic text-to-SQL layer means Genie generates SQL against mathematically stable scalar columns.
- Show the BEFORE and AFTER Genie runs. Same question, same interface. The gold columns carry the signal.

## Close: the lakehouse gains a relationship-aware primitive

- Every license, cluster hour, warehouse, and Genie seat the customer already pays for keeps working.
- Neo4j adds a small Aura instance and a silver-to-gold job. Three Delta columns appear in the gold layer. Every Databricks tool reads them.
- Questions that were out of reach at the row level become scalar-column queries.

## Headline

> Same Databricks spend. Strictly more answers.

## Handling scale questions

Refer the customer to [SCOPING_GUIDE.md](./SCOPING_GUIDE.md) for dataset sizing, Aura sizing, candidate-triage capacity, and base-rate-aware threshold calibration. Keep the slide focused on the three beats above.
