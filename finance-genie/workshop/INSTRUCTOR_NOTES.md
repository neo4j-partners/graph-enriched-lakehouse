# Instructor Notes

This document is for presenters. It is not linked from the participant notebooks.

---

## Why the framing matters

The demo makes a specific claim: the same Databricks spend, with Neo4j GDS as a
silver-to-gold enrichment stage, produces a catalog that answers a class of
analyst questions the base tables cannot reach.

The BEFORE questions are structural-discovery questions — hub detection,
community structure, merchant overlap. These questions cannot be answered from
the base tables because the answers live in network topology, not in any row or
column the base catalog carries. The structural gap is a property of what those
tables contain. Each miss is evidence of that property.

The AFTER questions are not the same questions. They are portfolio-composition,
cohort-comparison, rollup, operational, and merchant-side questions — the class
of BI questions an analyst would ask about any segment. After enrichment,
`community_id`, `fraud_risk_tier`, and `similarity_score` exist as scalar
columns. Genie reads them the same way it reads any other warehouse column.

The contrast is "wrong questions on base tables, right questions on enriched
tables." Not "same question, better answer."

---

## Common audience questions

### "Isn't Genie just doing `WHERE fraud_risk_tier = 'high'`?"

Yes. That is correct, and it is the point.

`fraud_risk_tier` is a scalar column written by the GDS pipeline based on
PageRank centrality. GDS computed the structural signal. `pull_gold_tables.py`
materialized it as a column. Genie is reading that column the same way it reads
any other Delta column.

The question reveals the right mental model: the enrichment pipeline did the
structural work; Genie is a text-to-SQL surface doing what it was designed to
do. The two systems are complementary, each doing its designed job.

### "Couldn't you just write a SQL join to get community membership?"

No. Community membership is the output of Louvain modularity optimization — a
global graph algorithm that maximizes within-community edge density while
minimizing cross-community edges. SQL cannot express transitive closure at ring
scale, and SQL transitive closure merges any rings that share a cross-ring
transfer, collapsing multiple rings into one giant component. Louvain keeps them
separated. The result is a stable `community_id` that groups all 100 ring
members together; SQL cannot produce this from the base tables.

### "Why didn't the BEFORE space find the fraud rings?"

It is not that Genie failed. It is that the base tables do not contain the
structural information needed to answer those questions. The tables have
`account_id`, `amount`, `merchant_id` — row-level transaction facts. They do not
have a column that encodes "this account is a hub in the transfer network" or
"these accounts form a community." Genie can only query what the tables contain.

### "The AFTER space is pointed at different tables — isn't that cheating?"

The AFTER space is pointed at the gold tables, which are Delta tables in Unity
Catalog written by `04_pull_gold_tables`. Those tables contain all the original
columns plus the three GDS-derived columns. The enrichment pipeline is the
contribution. Pointing the Genie Space at the enriched tables is the
demonstration of what the pipeline enables.

### "How does this scale to production data volumes?"

The structural-signal ratios — precision at top-20, max ring coverage, same-ring
fraction — are theoretically scale-invariant. They measure the signal-to-noise
ratio of the graph features, not the absolute counts. At production scale, the
GDS algorithms run on a larger graph; the ratio properties hold. See
`automated/SCOPING_GUIDE.md` for production-scale guidance.

---

## What the demo does not claim

- Genie did not gain the ability to detect fraud rings. GDS detected the
  structure. Genie reads the resulting columns.
- The demo does not prove the enrichment pipeline eliminates fraud. It
  demonstrates that structural analyst questions — previously unanswerable —
  become answerable after enrichment.
- The BEFORE misses are not Genie failures. They are catalog-structure
  limitations. Do not frame them as Genie failures in participant-facing
  language.
