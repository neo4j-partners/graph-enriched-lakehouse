# TALK_TRACK: Finance Genie field script

One slide of bullet points. Account teams and partner SEs read this off the slide. Pair with a live run of the BEFORE and AFTER Genie Spaces during the middle beat.

## Open: GDS fits naturally as a silver-to-gold enrichment stage

- The Databricks Lakehouse already runs medallion architecture, feature stores, and silver-to-gold transforms. GDS is another transform in that sequence.
- Its input is relationships from the silver tables. Its output is three scalar columns (`risk_score`, `community_id`, `similarity_score`) in the gold layer.
- The fraud use case is one instance. The same pattern covers entity resolution, supplier-network risk, recommendation structure, and compliance review.

## Middle: enrichment changes what questions make sense to ask

- BEFORE: the structural-discovery questions — find transfer hubs, find ring-like groups, find shared-merchant cohorts — return nothing useful on base tables. That is a framing problem, not a Genie failure. The answers live in network topology; no row-level SQL can surface them.
- Enrichment: GDS runs PageRank, Louvain, and Node Similarity and writes `risk_score`, `community_id`, `similarity_score` back into the gold layer. Structural discovery happens here, before Genie is ever asked anything.
- AFTER: the question class changes — portfolio composition by community, cohort comparisons across risk tiers, community rollups, operational workload by region, merchant-side analysis. Genie answers them because community and risk tier are now scalar dimensions it can group by, filter on, and rank. GDS discovered the structure; Genie characterizes it.
- The contrast is not "same question, better answer." It is "wrong framing on base tables, right framing on enriched tables."

## Close: the lakehouse gains a relationship-aware primitive

- Every license, cluster hour, warehouse, and Genie seat the customer already pays for keeps working.
- Neo4j adds a small Aura instance and a silver-to-gold job. Three Delta columns appear in the gold layer. Every Databricks tool reads them.
- Questions that were out of reach at the row level become scalar-column queries.

## Headline

> Same Databricks spend. Strictly more answers.

## Handling scale questions

Refer the customer to [SCOPING_GUIDE.md](./SCOPING_GUIDE.md) for dataset sizing, Aura sizing, candidate-triage capacity, and base-rate-aware threshold calibration. Keep the slide focused on the three beats above.
