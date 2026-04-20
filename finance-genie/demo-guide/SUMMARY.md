# FINAL_GUIDE Summary

## The Graph Enrichment Pipeline

Financial crime is a network problem: fraud rings are subgraphs that individual transaction records cannot expose on their own. The enrichment pipeline reads Silver tables, loads them into Neo4j as a property graph, runs GDS algorithms, and writes results back to the Gold layer as plain Delta columns Genie queries like any other dimension.

## What Genie Excels At

Genie translates analyst questions into SQL over Delta tables and excels at aggregation, grouping, filtering, ranking, and cohort comparisons. Its capability is unchanged after enrichment; what changes is that the Gold layer now carries structural dimensions Genie can operate against.

## What GDS Excels At

GDS answers three question classes with no SQL equivalent: centrality via PageRank, community membership via Louvain, and neighborhood similarity via Node Similarity. Each output is a scalar column per node, deterministic given a fixed graph projection, and stable across every Genie query run.

## How the Enrichment Pipeline Works

The pipeline loads Silver records into Neo4j, runs the three algorithms, and writes `risk_score`, `community_id`, and `similarity_score` back to the Gold layer as plain Delta columns. Every subsequent Genie query, dashboard, or downstream classifier reads those columns as ordinary dimensions with no graph query layer involved.

## Structural Segments vs. Structural Questions

Structural segment questions ask Genie to compare or aggregate over a structural column and produce self-explanatory answers within its designed envelope. Structural questions ask about network topology directly; the answers are correct but require graph-theory context the demo cannot carry, so the AFTER demo stays in the first category.

## Non-Deterministic SQL over a Deterministic Foundation

Genie's text-to-SQL translation is non-deterministic: the same question can produce different SQL shapes across runs, varying how much signal is retrieved but not whether it exists. GDS outputs are reproducible given a fixed graph projection, so the structural signal in the Gold columns is identical on every run.

## The Harder Problem: Silent Question Substitution

On structural-discovery questions against unenriched Silver tables, Genie answers with confidence but substitutes a proxy question it can answer in SQL for the structural question it cannot. After enrichment, ranking by `risk_score` descending is the correct retrieval of eigenvector centrality, not a proxy, and precision and recall on that question class recover fully.

## Proposed BEFORE Demo Questions

Ask standard BI questions first to show Genie working correctly, then structural-discovery questions to expose the gap where network topology does not exist in flat rows. After Genie substitutes on the second set, name what happened and explain that the enrichment pipeline is what changes.

## Proposed AFTER Demo Questions

Five question categories all produce answers unavailable from the BEFORE catalog and fall inside Genie's text-to-SQL envelope: portfolio composition, cohort comparisons, community rollups, operational workload, and merchant-side analysis. Recommended questions in each category have produced clean, self-explanatory results in live testing and require no graph-theory context to read.

## Where This Pattern Applies

The enrichment pattern fits any domain where the answer lives in relationships rather than individual rows: fraud-ring surfacing, entity resolution, supplier-network risk, recommendation structure, and compliance network review. GDS computes the structural quantity, the Gold layer carries it as a column, and every Databricks tool reads it without modification.

---

## Handling Tough Customer Questions

### "The fraud rate is 4%. Real fraud is 0.1%."

The dataset is a pedagogical compression calibrated to produce observable signal in a 20-minute window, not a production benchmark. The structural signal ratios GDS detects are theoretically invariant to base rate when ring mechanics scale proportionally; that invariance is the load-bearing claim.

### "Your dataset was built to make GDS succeed."

It was, and that is the right description. The honest claim is that structural signal is unreachable from tabular SQL and GDS converts it into columns; that claim holds at any base rate, any dataset size, and any ring construction.

### "GDS finds fraud. Can you prove that at scale?"

GDS produces three features with published mathematical definitions: eigenvector centrality, a modularity-optimal community partition, and Jaccard overlap. None of those is a fraud verdict; framing them as columns with reproducible computation is what gets through model risk management review.

### "What about false positives?"

Community purity averages 70%, meaning each ring-candidate community absorbs both ring members and non-ring accounts under the Louvain modularity objective. At production scale, the tier threshold is recalibrated against the customer's observed distribution; the pipeline shape does not change.

### "The ring construction is engineered for success."

The dataset is built to make structural signal observable inside a 20-minute window, not to benchmark production precision. The structural claim holds at any base rate and any ring calibration as long as the relationships exist in the data.

### "Everything looks too clean."

The dataset was constructed to produce clean results, and that should be named directly. The strong claim is that the structural signal class is unreachable from row-level SQL, not that production precision holds at realistic base rates.

### "There's no confuser population."

The synthetic data contains no dense non-ring communities that share merchant preferences for benign reasons, so every ring-candidate community is a real ring. At production scale, a confuser cohort exists in real data and the tier threshold is calibrated against the customer's observed distribution.
