# Gold Table Enrichment + GDS Calibration Record

> **Status (2026-04-16):** All four GDS pipeline checks pass against the live Neo4j AuraDS instance with Tier 5 parameters. PageRank fraud/normal ratio 3.65×, Louvain avg purity 80% with 100% ring coverage, NodeSimilarity ratio 1.98×. CSVs regenerated locally and verified (4/4). Upload to Databricks and notebook 03 rewrite are the remaining steps.

---

## Part 1 — GDS Calibration History

This section records what was tried, what failed, and why Tier 5 parameters are the current accepted state. The ground truth for active parameters is `setup/config.py`.

### The Fundamental Constraint

Density ratio and Louvain viability are mathematically linked and cannot be tuned independently at a fixed `NUM_P2P`:

```
density_ratio ≈ WITHIN_RING_PROB / (1 − WITHIN_RING_PROB) × 6,312
```

The multiplier 6,312 is fixed by dataset structure (25k accounts, 10 rings of 100). The only lever is `WITHIN_RING_PROB`. Louvain requires each ring member's neighborhood to be predominantly internal — which requires `WITHIN_RING_PROB` high enough that within-ring connections outnumber background connections. At `NUM_P2P=300k`, the practical minimum is `WITHIN_RING_PROB ≈ 0.10`. Real-world density (5–50x) requires Tier 2 scale (`NUM_P2P ≥ 2M`).

A secondary constraint: `CAPTAIN_TRANSFER_PROB` is a fraction of within-ring transfers, not total transfers. When `NUM_P2P` scales up, the absolute captain inbound grows proportionally. The value tuned for sparse rings (0.10 at `NUM_P2P=40k`) over-concentrates inbound at `NUM_P2P=300k`, making captains look like whales and breaking the whale-hiding check.

### Tier Summary

| Version | `WITHIN_RING_PROB` | `CAPTAIN_TRANSFER_PROB` | `RING_ANCHOR_PREF` | Density Ratio | Internal Edge Ratio | `verify` 4/4? | GDS 4/4? |
|---------|-------------------|-------------------------|--------------------|--------------|---------------------|---------------|----------|
| Original | 0.50 | 0.10 | 0.40 | 6,428× | 93% | ✅ | ✅ (trivially easy) |
| Tier 1 | 0.023 | 0.10 | 0.12 | 150× | 38% | ✅ | ❌ Louvain 19% |
| Demo Minimum | 0.10 | 0.10 | 0.12 | ~706× | 73% | ❌ captain≈whale | — |
| Tier 3 | 0.10 | **0.02** | 0.12 | 705× | 73% | ✅ | ❌ Louvain 4%, PageRank 0%, NodeSim 1.11× |
| Tier 4 | **0.25** | 0.02 | **0.25** | ~2,100× | ~89% | ✅ | ❌ Louvain 16%, NodeSim 1.50× |
| **Tier 5** | **0.35** | **0.02** | **0.35** | **~3,400×** | **~93%** | ✅ | ✅ **PageRank 3.65×, Louvain 80%, NodeSim 1.98×** |
| Tier 2 (future) | 0.003 | 0.20 | 0.05 | ~20× | ~4% | Requires threshold changes | Requires `NUM_P2P=2M` |

### Key Discoveries During Testing

**Tier 1 failure — Louvain cannot work at 38% internal edge ratio.** Lowering `WITHIN_RING_PROB` to 0.023 produced a density ratio of 150× but only 38% of each ring member's connections stayed within the ring. Louvain's modularity optimization merged rings into giant background communities (avg purity 19%). Coverage was 96% — rings were structurally detectable — but communities were too impure to use. This established the practical floor: `WITHIN_RING_PROB` must be at least 0.08–0.10 at `NUM_P2P=300k`.

**Bidirectional projection filter failed.** To improve Louvain purity we attempted projecting only account pairs with transfers in both directions, theoretically stripping ring-to-whale bridges while preserving structured ring relationships. The result: only 231 of 25,000 accounts had mutual transfers. The generator draws random within-ring pairs and never forces reciprocal edges, so the filter removed most of the ring structure. Coverage dropped from 99–100% to 72–86% with each ring fragmenting across 7–13 communities. Reverted to UNDIRECTED native projection.

**CAPTAIN_TRANSFER_PROB miscalibration at scale.** The captain routing probability of 0.10 was set when `NUM_P2P=40k` — it routed ~2,000 intra-ring transfers to 50 captains, keeping captains below whale inbound. At `NUM_P2P=300k` the same probability routes 30,000 × 0.10 = 3,000 transfers to 50 captains (60 per captain), which at `WITHIN_RING_PROB=0.10` nearly equaled whale avg inbound of 83.5. The fix: reduce to 0.02, providing a light hierarchy signal (~12 extra inbound per captain) without competing with whales on raw degree.

**Node Similarity noise floor — small merchant universe.** At `NUM_MERCHANTS=2,500` with 25,000 accounts each visiting ~10 merchants, every merchant had ~100 customers. Random coincidental 2-merchant overlap produced a noise floor for all accounts at similarity ≈ 0.14. Ring members' top-10 SIMILAR_TO neighbors were random coincidental pairs, not ring-mates, because random pairs scored higher than same-ring pairs with `RING_ANCHOR_PREF=0.09–0.18`. The fix: `NUM_MERCHANTS=7,500` (reduces customers-per-merchant from 100 to 33, collapsing the noise floor) and `RING_ANCHOR_PREF=0.35` (ring members direct 35% of spend to shared anchors, making intra-ring Jaccard clearly distinct).

**Hidden `.env` override.** `finance-genie/setup/.env` contained Phase 2 weak-signal parameters that silently overrode `config.py` values, including `RING_ANCHOR_PREF=0.09` when `config.py` had 0.40. This caused three failures — Node Similarity 1.01×, Louvain at 46–50%, PageRank 0% — that were misattributed to GDS configuration. The `.env` was cleaned; `config.py` values are now the active defaults.

**PageRank top-20 check is incompatible with whale-hiding.** The original GDS check required ≥50% of top-20 accounts by `risk_score` to be fraud. This is structurally incompatible with the demo narrative: the entire "before GDS" story is that sorting by inbound volume surfaces whales. Since undirected PageRank is dominated by the same high-inbound accounts, whales occupy the top-20 by design. The check was changed to a distribution-wide fraud/normal ratio (≥3.0×), which measures the genuine score separation across the full population rather than a tail slice.

### Current Accepted State (Tier 5)

Active parameters in `setup/config.py`:

| Parameter | Value | Notes |
|-----------|-------|-------|
| `NUM_P2P` | 300,000 | Sufficient scale for ring signal |
| `NUM_MERCHANTS` | 7,500 | Reduces coincidental Jaccard noise floor |
| `WITHIN_RING_PROB` | 0.35 | 93% internal edge ratio; Louvain 80% avg purity |
| `CAPTAIN_TRANSFER_PROB` | 0.02 | Light hierarchy signal; captains well below whale inbound |
| `WHALE_INBOUND` | 0.14 | Whale avg ~218 inbound; ~1.4× above captain inbound |
| `WHALE_OUTBOUND` | 0.14 | Symmetric |
| `RING_ANCHOR_PREF` | 0.35 | Ring members clearly distinct from noise floor in NodeSim |
| `RING_ANCHOR_CNT` | 4 | Unchanged |

`verify_fraud_patterns.py` results (2026-04-16, all 4/4 pass):

| Check | Key metric | Measured | Threshold |
|-------|-----------|---------|-----------|
| Whale-Hiding-PageRank | top_200_whales | 199 | ≥ 180 ✅ |
| Whale-Hiding-PageRank | top_200_fraud_members | 1 | ≤ 20 ✅ |
| Ring Density Ratio | within-ring / background | 705.8× | ≥ 100 ✅ |
| Anchor Jaccard | within-ring / cross-ring | 22.81× | ≥ 1.4 ✅ |
| Column Signal Sanity | high-risk fraction gap | 0.13 pp | < 5 pp ✅ |

`run_and_verify_gds.py` results (2026-04-16, all 4/4 pass):

| Check | Metric | Measured | Threshold |
|-------|--------|---------|-----------|
| PageRank fraud/normal ratio | `fraud_avg / normal_avg` risk_score | 3.65× | ≥ 3.0× ✅ |
| Louvain avg purity | across 10 rings | 80% | ≥ 50% ✅ |
| Louvain per-ring coverage | fraction in dominant community | 100% | ≥ 80% ✅ |
| NodeSimilarity fraud/normal ratio | `fraud_avg / normal_avg` similarity | 1.98× | ≥ 1.9× ✅ |

Louvain: all 10 rings form tight, distinct communities (73–88% purity, 113–137 members each). No large background community absorption.

### Realism Assessment

| Metric | Tier 5 (current) | Real World | Notes |
|--------|-----------------|------------|-------|
| Density ratio | ~3,400× | 5–50× | Still 2× better than Original 6,428×. Basic SQL finds only ~0.2% of ring pairs (Poisson avg 0.30 transfers/pair) — graph algorithms are genuinely needed. |
| Jaccard ratio | ~22.8× | 2–5× | Anchor signal is amplified. Real mule accounts diversify more deliberately. |

This is a defensible demo: Genie's raw inbound-sort correctly surfaces whales (not rings), and graph algorithms must do genuine work to recover the ring structure. The signals are amplified relative to production — Tier 2 scale (`NUM_P2P=2M+`) would bring the density ratio into realistic range but requires a different infrastructure setup.

### Validation Scripts

`validate_neo4j.py` — fast credential and connectivity check. Run when `.env` or the Aura instance changes.

`validate_neo4j_graph.py` — structural check of the ingested graph: node/edge counts, per-ring density, anchor visit ratios vs `data/ground_truth.json`. Run after any notebook 01 execution.

`validate_gds_output.py` — read-only diagnostic of GDS-written properties. Checks feature completeness, fraud/normal separation, `SIMILAR_TO` relationship count. Note: uses the original aspirational Louvain threshold (80% purity) — expected to produce Louvain failures against current data. Use `run_and_verify_gds.py` for the authoritative check.

`run_and_verify_gds.py` — runs the full GDS pipeline from Python against the live Neo4j AuraDS instance, then executes per-ring Louvain diagnostics and all four verification checks. This is the gate for upload approval.

---

## Part 2 — Gold Table Enrichment Proposal

### The Problem

`gold_accounts.risk_score` sorts whales to the top, not fraud ring members. PageRank on an undirected transfer graph rewards volume: whale accounts receive 75–85 inbound transfers and score 20–25. Ring members receive 35–45 inbound transfers and score 2.1–2.6. A naive `ORDER BY risk_score DESC` returns the legitimate high-volume accounts that the demo is designed to show are *not* the fraud signal.

The correct query is a two-step subquery: identify communities of 50–200 members with average `risk_score > 1.0`, then rank accounts within those communities by `risk_score`. The current Genie space instructions document this pattern, but Genie reconstructs it from scratch on every question and frequently generates a simpler single-sort query instead. The failure is not Genie's SQL capability. The fraud signal requires a join that no raw column exposes directly.

The fix is to compute that join once in `03_pull_gold_tables.ipynb` and write the result into the gold tables. Every question Genie asks about fraud risk then reduces to a filter on a pre-labeled column.

All labeling below uses GDS outputs only. `account_labels.csv` is not read.

---

### Open Questions — Implementation

**Q1. `fillna(0)` clobbers `community_id`.**
The final `.fillna(0)` in `gold_df` zeroes out `community_id` for every account that has no GDS graph features. All such accounts land in a synthetic "community 0," and the window functions then compute `community_size`, `community_avg_risk_score`, and `community_risk_rank` over that artificial cluster. Should `.fillna(0)` be replaced with a targeted `fillna({"inbound_transfer_count": 0})` that leaves graph columns null for unscored accounts? Or should `community_id` be filled with `-1` to mark unassigned accounts explicitly?

**Q2. `RANK()` in `top_accounts` can return multiple rows per community.**
`top_accounts` uses `F.rank().over(Window.partitionBy("community_id").orderBy(F.desc("risk_score")))`. When two accounts share the same `max_risk_score`, both receive rank 1 and the subsequent left join produces duplicate rows in `ring_communities_df`. Should this use `ROW_NUMBER()` to guarantee exactly one `top_account_id` per community?

**Q3. Section ordering dependency for Change 3 is implicit.**
Change 3 builds `community_lookup` by reading from `GOLD_FEATURES_TABLE_QUALIFIED` (gold_accounts). That read requires gold_accounts to already be written to the catalog. The notebook must write gold_accounts at the end of section 6, then read it back in sections 7 and 8. Is that ordering currently enforced, or does section 7 build `similarity_pairs_df` before the table is written?

**Q4. `same_community` null check is one-sided.**
The derivation checks `F.col("community_id_a").isNotNull()` but not `community_id_b`. Two accounts both excluded from the GDS projection would have null community IDs; the `==` comparison returns null (not false), so `same_community` would be null rather than false for that pair. Is that acceptable, or should the condition require both sides to be non-null before testing equality?

**Q5. `gold_fraud_ring_communities` must be registered in the Genie space.**
The proposal updates `GENIE_SETUP.md` with instructions that describe the new table, but Genie spaces have an explicit table configuration separate from the instruction text. A new table must be added to the space's allowed tables before Genie can query it. Is that step handled elsewhere, or does it need to be added to the implementation checklist?

**Q6. What fraction of ring members land in `'medium'` vs `'high'`?**
`'medium'` captures ring members excluded from the Node Similarity bipartite projection by `degreeCutoff=5`. At `RING_ANCHOR_CNT=4` with `RING_ANCHOR_PREF=0.35`, some ring members visit fewer than five distinct merchants. If that fraction exceeds roughly 20% of the 1,000 simulated ring members, demo queries for "which accounts are highest fraud risk?" return a noticeably incomplete set of `'high'` tier accounts. This has not been measured against the current Tier 5 parameters.

---

### Critical Review — Will This Help Genie?

**The core bet is correct.** Genie's failure mode on fraud questions is not SQL capability; it is schema legibility. A single `WHERE fraud_risk_tier = 'high'` predicate is unambiguous in a way that a community subquery with `HAVING COUNT(*) BETWEEN 50 AND 200` is not. Pre-computing the join removes the reconstruction problem entirely, and that is the right fix.

**`fraud_risk_tier` is the highest-value change in the proposal.** It collapses a two-step community-membership test into a filter on a single labeled column. Genie cannot misinterpret it. Every fraud-risk question becomes a predicate on a string column, not a multi-table join. The column earns its place.

**`gold_fraud_ring_communities` is the second highest-value change.** Ring-count, ring-severity, and ring-captain questions are currently impossible for Genie to answer reliably because they require aggregation with a `HAVING` filter that Genie must reconstruct correctly every time. A pre-aggregated table removes that reconstruction entirely. The value is real, but it lands only if Q5 above is answered — the table must actually be registered in the Genie space configuration, not just described in the instruction text.

**`same_community` in the similarity pairs table has limited standalone value.** Genie can already join two tables. The harder problem for similarity-pair questions is that account pairs are a less natural entry point for fraud questions than accounts or rings. The column is low-risk to add but should not be treated as a meaningful contribution to Genie reliability.

**The Genie space instructions are necessary but not sufficient.** The proposal documents column semantics carefully, and that matters for grounding Genie's generated SQL. But Genie's adherence to free-text instructions is inconsistent across question phrasings and session resets. The pre-computed columns are the durable fix. The instructions reinforce them; they do not substitute for them.

**Threshold risk deserves a pre-demo check.** `community_size BETWEEN 50 AND 200` is tuned to 100-member simulated rings. If data generation produces any rings at 48 or 203 members due to isolation or seeding variance, those rings receive `is_ring_candidate = false` and `fraud_risk_tier = 'low'` despite being real fraud rings. Verification step 2 catches this, but the check must run before any public demo showing. A failed ring-count query returning 8 instead of 10 would undermine the demo's central claim.

---

### Change 1: Extend `gold_accounts` with Community Aggregates and a Fraud Tier Label

Six new columns join the existing ten. Four are window functions over `community_id`. One is an `account_links` aggregate. One is a derived label.

| Column | Type | Derivation |
|---|---|---|
| `community_size` | INT | `COUNT(*) OVER (PARTITION BY community_id)` |
| `community_avg_risk_score` | DOUBLE | `AVG(risk_score) OVER (PARTITION BY community_id)` |
| `community_risk_rank` | INT | `RANK() OVER (PARTITION BY community_id ORDER BY risk_score DESC)` |
| `inbound_transfer_count` | INT | Count of `account_links` rows where `dst_account_id = account_id` |
| `is_ring_community` | BOOLEAN | `community_size BETWEEN 50 AND 200 AND community_avg_risk_score > 1.0` |
| `fraud_risk_tier` | STRING | `'high'` / `'medium'` / `'low'` (see below) |

#### Fraud Tier Derivation

```sql
CASE
  WHEN community_size BETWEEN 50 AND 200
   AND community_avg_risk_score > 1.0
   AND risk_score > 0.5
   AND similarity_score > 0.05  THEN 'high'
  WHEN community_size BETWEEN 50 AND 200
   AND community_avg_risk_score > 1.0  THEN 'medium'
  ELSE 'low'
END
```

`'high'` requires all three GDS signals to converge: the account belongs to a ring-sized community, carries individual PageRank above noise, and shares merchant patterns with other accounts. `'medium'` captures ring members who lack a personal similarity score, typically because Node Similarity's `degreeCutoff=5` excluded them from the bipartite projection. `'low'` covers everything else.

#### What This Enables for Genie

- "Which accounts are highest fraud risk?" → `WHERE fraud_risk_tier = 'high' ORDER BY risk_score DESC`
- "Who leads each fraud ring?" → `WHERE fraud_risk_tier IN ('high', 'medium') AND community_risk_rank = 1`
- "Show me all accounts in suspicious communities" → `WHERE is_ring_community = true`

#### Implementation

In `feature_engineering/03_pull_gold_tables.ipynb`, Section 6:

```python
from pyspark.sql import Window
from pyspark.sql import functions as F

inbound_counts = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.account_links")
    .groupBy(F.col("dst_account_id").alias("account_id"))
    .agg(F.count("*").alias("inbound_transfer_count"))
)

w_community = Window.partitionBy("community_id")
w_rank      = Window.partitionBy("community_id").orderBy(F.desc("risk_score"))

gold_df = (
    spark.table(f"`{CATALOG}`.`{SCHEMA}`.accounts")
    .join(graph_feat, "account_id", "left")
    .join(inbound_counts, "account_id", "left")
    .fillna({"inbound_transfer_count": 0})
    .withColumn("community_size",          F.count("*").over(w_community))
    .withColumn("community_avg_risk_score", F.avg("risk_score").over(w_community))
    .withColumn("community_risk_rank",      F.rank().over(w_rank))
    .withColumn("is_ring_community",
        (F.col("community_size").between(50, 200)) &
        (F.col("community_avg_risk_score") > 1.0)
    )
    .withColumn("fraud_risk_tier",
        F.when(
            F.col("is_ring_community") &
            (F.col("risk_score") > 0.5) &
            (F.col("similarity_score") > 0.05), "high"
        ).when(
            F.col("is_ring_community"), "medium"
        ).otherwise("low")
    )
    .select(
        "account_id", "account_hash", "account_type", "region",
        "balance", "opened_date", "holder_age",
        "risk_score", "community_id", "similarity_score",
        "community_size", "community_avg_risk_score", "community_risk_rank",
        "inbound_transfer_count", "is_ring_community", "fraud_risk_tier",
    )
    .fillna(0)
)
```

---

### Change 2: New `gold_fraud_ring_communities` Table

`gold_accounts` answers questions about individual accounts. Genie also receives questions about rings as units: "how many fraud rings did GDS find?", "which ring has the most members?", "show the ring with the highest average risk." Pre-aggregating into a summary table removes the aggregation from Genie's query path entirely.

#### Schema

| Column | Type | Notes |
|---|---|---|
| `community_id` | BIGINT | Louvain cluster ID |
| `member_count` | INT | Total accounts in community |
| `avg_risk_score` | DOUBLE | Mean PageRank within community |
| `max_risk_score` | DOUBLE | Highest PageRank (captain proxy) |
| `avg_similarity_score` | DOUBLE | Mean Jaccard score within community |
| `high_risk_member_count` | INT | Members with `risk_score > 1.0` |
| `is_ring_candidate` | BOOLEAN | `member_count BETWEEN 50 AND 200 AND avg_risk_score > 1.0` |
| `top_account_id` | BIGINT | `account_id` with `max_risk_score` within this community |

#### What This Enables for Genie

- "How many fraud rings did GDS identify?" → `SELECT COUNT(*) FROM gold_fraud_ring_communities WHERE is_ring_candidate = true`
- "Show me all suspected fraud rings ranked by severity" → `SELECT * FROM gold_fraud_ring_communities WHERE is_ring_candidate = true ORDER BY avg_risk_score DESC`
- "Who leads each ring?" → answered directly by `top_account_id` without a self-join

#### Implementation

Add Section 8 to `03_pull_gold_tables.ipynb`, after the gold tables are written:

```python
RING_COMMUNITIES_TABLE = f"`{CATALOG}`.`{SCHEMA}`.gold_fraud_ring_communities"

ring_communities_df = (
    spark.table(GOLD_FEATURES_TABLE_QUALIFIED)
    .groupBy("community_id")
    .agg(
        F.count("*").alias("member_count"),
        F.round(F.avg("risk_score"), 6).alias("avg_risk_score"),
        F.round(F.max("risk_score"), 6).alias("max_risk_score"),
        F.round(F.avg("similarity_score"), 5).alias("avg_similarity_score"),
        F.sum(F.when(F.col("risk_score") > 1.0, 1).otherwise(0))
            .alias("high_risk_member_count"),
    )
    .withColumn(
        "is_ring_candidate",
        F.col("member_count").between(50, 200) & (F.col("avg_risk_score") > 1.0)
    )
)

top_accounts = (
    spark.table(GOLD_FEATURES_TABLE_QUALIFIED)
    .select("community_id", "account_id", "risk_score")
    .withColumn("_rank", F.rank().over(
        Window.partitionBy("community_id").orderBy(F.desc("risk_score"))
    ))
    .filter(F.col("_rank") == 1)
    .select(F.col("community_id"), F.col("account_id").alias("top_account_id"))
)

ring_communities_df = ring_communities_df.join(top_accounts, "community_id", "left")

(ring_communities_df
 .write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true")
 .saveAsTable(RING_COMMUNITIES_TABLE)
)
```

---

### Change 3: Add `same_community` to `gold_account_similarity_pairs`

One boolean column closes the gap for "high-similarity pairs that are also inside the same fraud ring" without requiring a join back to `gold_accounts`.

| New Column | Type | Derivation |
|---|---|---|
| `same_community` | BOOLEAN | Community IDs match for both accounts in the pair |

#### What This Enables for Genie

- "Which pairs of accounts share similar merchant patterns and are in the same suspicious ring?" → `WHERE same_community = true AND similarity_score > 0.10 ORDER BY similarity_score DESC`

#### Implementation

Extend Section 7 in `03_pull_gold_tables.ipynb` before writing the pairs table:

```python
community_lookup = (
    spark.table(GOLD_FEATURES_TABLE_QUALIFIED)
    .select("account_id", "community_id")
)

similarity_pairs_df = (
    similarity_pairs_df
    .join(community_lookup.withColumnRenamed("account_id", "account_id_a")
                          .withColumnRenamed("community_id", "community_id_a"),
          "account_id_a", "left")
    .join(community_lookup.withColumnRenamed("account_id", "account_id_b")
                          .withColumnRenamed("community_id", "community_id_b"),
          "account_id_b", "left")
    .withColumn("same_community",
        F.col("community_id_a").isNotNull() &
        (F.col("community_id_a") == F.col("community_id_b"))
    )
    .drop("community_id_a", "community_id_b")
)
```

---

### Updated Genie Space Instructions

Add to the column reference section of `GENIE_SETUP.md`:

```
gold_accounts.fraud_risk_tier (STRING: 'high', 'medium', 'low')
GDS-derived fraud label. 'high': ring-sized community (50–200 members, avg risk_score > 1.0)
AND individual risk_score > 0.5 AND similarity_score > 0.05. 'medium': in a ring-community
but lacks similarity signal. 'low': everything else.
- Use as primary filter for fraud questions: WHERE fraud_risk_tier = 'high'
- Do not use risk_score DESC alone — it returns whales, not ring members

gold_accounts.is_ring_community (BOOLEAN)
True when the account's Louvain community has 50–200 members and avg risk_score > 1.0.

gold_accounts.community_size (INT)
Number of accounts sharing this community_id. Pre-computed — no GROUP BY needed.

gold_accounts.community_avg_risk_score (DOUBLE)
Average PageRank within this community. Pre-computed.

gold_accounts.community_risk_rank (INT)
Rank of this account by risk_score within its community. 1 = highest (the captain).

gold_accounts.inbound_transfer_count (INT)
Number of incoming P2P transfers from account_links.

gold_fraud_ring_communities (table)
One row per Louvain community that is a ring candidate (50–200 members, avg_risk_score > 1.0).
Columns: community_id, member_count, avg_risk_score, max_risk_score, avg_similarity_score,
high_risk_member_count, is_ring_candidate, top_account_id.

gold_account_similarity_pairs.same_community (BOOLEAN)
True when both accounts in the pair share the same community_id.
```

Replace the "Answering Common Fraud Questions" examples with:

```
"Which accounts are highest fraud risk?"
→ SELECT account_id, risk_score, community_id, community_risk_rank, inbound_transfer_count
  FROM gold_accounts WHERE fraud_risk_tier = 'high' ORDER BY risk_score DESC LIMIT 20

"Who leads each fraud ring?"
→ SELECT account_id, community_id, risk_score, inbound_transfer_count
  FROM gold_accounts WHERE fraud_risk_tier IN ('high', 'medium') AND community_risk_rank = 1
  ORDER BY risk_score DESC

"How many fraud rings did GDS find?"
→ SELECT COUNT(*) AS ring_count FROM gold_fraud_ring_communities WHERE is_ring_candidate = true

"Show me all suspected fraud rings"
→ SELECT community_id, member_count, avg_risk_score, high_risk_member_count, top_account_id
  FROM gold_fraud_ring_communities WHERE is_ring_candidate = true ORDER BY avg_risk_score DESC

"Which high-similarity account pairs are inside the same ring?"
→ SELECT account_id_a, account_id_b, similarity_score
  FROM gold_account_similarity_pairs WHERE same_community = true AND similarity_score > 0.10
  ORDER BY similarity_score DESC LIMIT 20
```

---

### Tradeoffs

**The fraud tier thresholds are tuned to this dataset.** `community_size BETWEEN 50 AND 200` was chosen because each simulated ring has 100 members. Real fraud ring sizes vary. At production scale these bounds should be derived from historical ring investigations rather than hardcoded.

**`fraud_risk_tier = 'high'` has false negatives by design.** The `similarity_score > 0.05` requirement excludes ring members below Node Similarity's `degreeCutoff=5` threshold. At Tier 5 parameters, some ring members visit fewer than five distinct merchants and are excluded from the bipartite projection. Those accounts correctly land in `'medium'`. Lowering `degreeCutoff` in `02_aura_gds_guide.ipynb` would recover them but increases Neo4j computation time.

**`gold_fraud_ring_communities` is a materialized snapshot.** It reflects the GDS run from which `gold_accounts` was built. Re-running GDS produces new community IDs — both tables must be rebuilt together or `top_account_id` and `community_id` references go stale.

---

### Verification

After updating `03_pull_gold_tables.ipynb` and re-running it:

1. Spot-check `gold_accounts` — confirm `fraud_risk_tier = 'high'` accounts have `community_size BETWEEN 50 AND 200` and `community_avg_risk_score > 1.0`. Confirm `community_risk_rank = 1` per community returns exactly one account.

2. Check `gold_fraud_ring_communities` — `SELECT COUNT(*) WHERE is_ring_candidate = true` should return 10 (matching `N_RINGS = 10`). Each ring's `member_count` should be near 100. `top_account_id` should be a ring member per `ground_truth.json`.

3. Re-run `genie_demos/gds_enrichment_closes_gaps.ipynb` and confirm the three validation checks still pass:
   - Check 1 (PageRank): precision at top-20 > 70%
   - Check 2 (Louvain): max_ring_coverage > 80%
   - Check 3 (Node Similarity): same_ring_fraction > 60%

4. Run three Genie queries manually against the updated space:
   - "Which accounts are highest fraud risk?" — result should be dominated by `fraud_risk_tier = 'high'` accounts, not whales
   - "How many fraud rings did GDS find?" — should return 10
   - "Which high-similarity pairs are in the same suspicious ring?" — result should be same-ring pairs with similarity > 0.10
