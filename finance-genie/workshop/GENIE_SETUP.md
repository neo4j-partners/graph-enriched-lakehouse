# Genie Space Setup — After GDS Enrichment

This guide covers the second Genie space: the one built over the GDS-enriched gold tables that closes the three gaps demonstrated in the `workshop/` demo notebooks.

The first space (raw tables) shows Genie failing. This second space shows Genie succeeding — but only if it knows what `risk_score`, `community_id`, and `similarity_score` mean. Without explicit instructions, Genie treats them as generic numeric columns and generates queries that miss the point. The instructions in this guide fix that.

---

## Prerequisites

Both gold tables must exist before you create the space.

Run `workshop/02_aura_gds_guide.ipynb` in the Neo4j Aura Workspace to compute PageRank, Louvain, and Node Similarity. Then run `workshop/03_pull_gold_tables.ipynb` sections 6 and 7 to pull the enriched nodes from Neo4j and write the two gold tables to Delta.

Verify the tables exist before continuing:

```sql
SELECT COUNT(*) FROM `graph-enriched-lakehouse`.`graph-enriched-schema`.gold_accounts;
SELECT COUNT(*) FROM `graph-enriched-lakehouse`.`graph-enriched-schema`.gold_account_similarity_pairs;
```

Both queries must return rows. If either is empty, re-run the corresponding section.

---

## Create the Genie Space

In the Databricks workspace, navigate to **Genie** and create a new space. Name it something that distinguishes it from the raw-tables space, for example:

```
Fraud Ring Detection — After GDS Enrichment
```

---

## Tables to Connect

Add all seven tables to the space. The gold tables are the primary data sources; the base tables enable combined queries.

| Table | Catalog / Schema | Role |
|-------|-----------------|------|
| `gold_accounts` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account metadata + GDS features + pre-computed community aggregates and fraud tier label |
| `gold_account_similarity_pairs` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Jaccard similarity pairs with `same_community` flag |
| `gold_fraud_ring_communities` | `graph-enriched-lakehouse` / `graph-enriched-schema` | One row per ring-candidate community; pre-aggregated ring stats and captain account |
| `transactions` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account-to-merchant payment events |
| `account_links` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account-to-account transfer edges |
| `accounts` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Raw account dimension (demographics, balance, type) |
| `merchants` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Merchant dimension |

> **Do not add `account_labels` to this space.** It contains the ground-truth `is_fraud` column. If it is connected, Genie will join against it to answer fraud questions, which makes the demo circular — Genie finds fraud because it can see the fraud labels, not because the graph features work. Ground-truth validation is handled by the demo notebook: Genie returns account IDs, and the notebook joins those IDs against `account_labels` outside of Genie to measure precision.

---

## Instructions for the Genie Space

Paste the following into the **Instructions** field of the space. These instructions tell Genie what the GDS-computed columns mean and how to use them. Without them, Genie will not know to sort by `risk_score` for hub detection, group by `community_id` for ring detection, or query `gold_account_similarity_pairs` for merchant similarity.

---

```
This space is connected to a fraud detection dataset enriched with three graph features computed by Neo4j Graph Data Science. Understanding these features is required to answer fraud questions correctly.

## Graph Features

**gold_accounts.risk_score** (DOUBLE, fraud ring captains: 2.1–2.6, high-volume legitimate accounts: 20–25)
PageRank centrality computed on the account-to-account transfer graph. Accounts that receive transfers from other high-scoring accounts score higher. Fraud ring captain accounts score 2.1–2.6 because ring topology recursively amplifies centrality among ring members. High-volume legitimate accounts (whales) score 20–25 because their large number of inbound transfers inflates raw PageRank even though those senders are peripheral low-centrality nodes.
- Do not sort by risk_score DESC alone to find fraud. The highest raw scores belong to legitimate high-volume accounts, not fraud ring members.
- Use fraud_risk_tier as the primary filter for fraud questions (see below), then rank within results by risk_score DESC.
- Do not use transfer count or inbound transfer amount as a proxy for this column. Volume and centrality are different things.

**gold_accounts.community_id** (BIGINT)
Louvain community label. Every account in the same fraud ring shares a single community_id. Accounts in different rings have different IDs. Normal accounts are assigned IDs for communities they naturally form but these communities are small and sparse compared to fraud rings.
- Use this column to identify fraud rings. GROUP BY community_id to surface ring-level structure.
- Do not attempt to detect rings using bilateral transfer pairs or recursive CTEs. The community_id column encodes ring membership directly.
- A community with 50 or more members and high internal transfer density is a fraud ring candidate.

**gold_accounts.similarity_score** (DOUBLE, range 0–1)
Node Similarity (Jaccard) score. Represents the maximum Jaccard similarity this account has with any other account based on shared merchant visits. Fraud ring members share a set of anchor merchants and score higher than high-volume normal accounts whose shared-merchant count is diluted by large merchant footprints.
- This column shows the per-account maximum similarity. For pairwise analysis, use gold_account_similarity_pairs instead.

## Pre-Computed Fraud Labels

**gold_accounts.fraud_risk_tier** (STRING: 'high', 'medium', 'low')
GDS-derived fraud label combining all three graph signals. Use this as the primary filter for fraud questions.
- 'high': ring-sized community (50–200 members, community_avg_risk_score > 1.0) AND risk_score > 0.5 AND similarity_score > 0.05
- 'medium': in a ring-sized community but lacks individual similarity signal — Node Similarity excluded this account due to low merchant visit count
- 'low': everything else
- Do not use risk_score DESC alone — it returns whales, not ring members

**gold_accounts.is_ring_community** (BOOLEAN)
True when the account's Louvain community has 50–200 members and community_avg_risk_score > 1.0.

**gold_accounts.community_size** (INT)
Number of accounts sharing this community_id. Pre-computed — no GROUP BY needed.

**gold_accounts.community_avg_risk_score** (DOUBLE)
Average PageRank within this community. Pre-computed.

**gold_accounts.community_risk_rank** (INT)
Rank of this account by risk_score within its community. 1 = highest (the ring captain).

**gold_accounts.inbound_transfer_count** (INT)
Number of incoming P2P transfers from account_links.

## Pairwise Similarity Table

**gold_account_similarity_pairs** contains one row per account pair with columns account_id_a, account_id_b, similarity_score, and same_community. These pairs were computed using Jaccard normalization over shared merchant visits.
- For questions about which accounts share the most similar merchant patterns, query this table and sort by similarity_score DESC.
- Do not rank pairs by raw shared-merchant count. High-volume normal accounts accumulate many shared merchants by chance. Jaccard normalization corrects for merchant footprint size.
- Same-ring account pairs score around 0.18–0.22 Jaccard. High-volume normal pairs score lower because Jaccard normalization penalizes large merchant footprints. The normalized score separates them; raw count does not.
- same_community = true when both accounts share the same community_id. Use with similarity_score to find high-similarity pairs inside a ring.

## Ring Summary Table

**gold_fraud_ring_communities** contains one row per Louvain community that is a ring candidate (50–200 members, avg_risk_score > 1.0). Use this table for ring-level questions — it removes the need to GROUP BY community_id on gold_accounts.
- top_account_id identifies the highest-PageRank account (captain) in each ring directly.
- is_ring_candidate = true flags communities that meet the size and risk thresholds.

## Answering Common Fraud Questions

"Which accounts have the highest fraud risk?"
→ SELECT account_id, risk_score, community_id, community_risk_rank, inbound_transfer_count
  FROM gold_accounts WHERE fraud_risk_tier = 'high' ORDER BY risk_score DESC LIMIT 20

"Who leads each fraud ring?"
→ SELECT account_id, community_id, risk_score, inbound_transfer_count
  FROM gold_accounts WHERE fraud_risk_tier IN ('high', 'medium') AND community_risk_rank = 1
  ORDER BY risk_score DESC

"How many fraud rings did GDS find?"
→ SELECT COUNT(*) AS ring_count FROM gold_fraud_ring_communities WHERE is_ring_candidate = true

"Show me all suspected fraud rings ranked by severity"
→ SELECT community_id, member_count, avg_risk_score, high_risk_member_count, top_account_id
  FROM gold_fraud_ring_communities WHERE is_ring_candidate = true ORDER BY avg_risk_score DESC

"Show me the members of a specific fraud ring community"
→ SELECT * FROM gold_accounts WHERE community_id = <id> ORDER BY risk_score DESC

"Which pairs of accounts share the most similar merchant visit patterns?"
→ SELECT account_id_a, account_id_b, similarity_score FROM gold_account_similarity_pairs ORDER BY similarity_score DESC LIMIT 20

"Which high-similarity account pairs are inside the same ring?"
→ SELECT account_id_a, account_id_b, similarity_score
  FROM gold_account_similarity_pairs WHERE same_community = true AND similarity_score > 0.10
  ORDER BY similarity_score DESC LIMIT 20

## Column Reference

gold_accounts: account_id, account_hash, account_type, region, balance, opened_date, holder_age, risk_score, community_id, similarity_score, community_size, community_avg_risk_score, community_risk_rank, inbound_transfer_count, is_ring_community, fraud_risk_tier

gold_account_similarity_pairs: account_id_a, account_id_b, similarity_score, same_community

gold_fraud_ring_communities: community_id, member_count, avg_risk_score, max_risk_score, avg_similarity_score, high_risk_member_count, is_ring_candidate, top_account_id
```

---

## Connect the Notebook

Open `workshop/gds_enrichment_closes_gaps.ipynb` and find the configuration cell:

```python
SPACE_ID = "YOUR-GENIE-SPACE-ID"  # <-- replace this
```

Copy the space ID from the Genie space URL. The URL has the form:

```
https://<workspace-host>/genie/spaces/<space-id>
```

Paste the ID into the cell and run the notebook. The notebook sends three questions to Genie and validates the results against ground truth:

- Check 1: PageRank hub detection — precision at top-20 must exceed 70%
- Check 2: Louvain community structure — max ring coverage must exceed 80%
- Check 3: Node Similarity ring pairs — same-ring fraction must exceed 60%

All three checks should pass if the GDS algorithms ran successfully and the space instructions are in place.

---

## Before: Genie Without Graph Enrichment

This is what Genie returned when queried against the raw tables — before GDS enrichment and before the gold tables existed.

**Question asked:** "Are there accounts acting as hubs of potentially fraudulent money movement networks?"

**Genie's answer:** Yes — 20 accounts flagged as fraudulent hubs.

| Account | Transfers | Outgoing | Incoming | High-Risk Txns % | Risk Score |
|---------|-----------|----------|----------|-----------------|------------|
| 16078 | 71 | $24,079 | $12,762 | 53.85% | 36.49 |
| 4940 | 84 | $19,533 | $10,628 | 54.55% | 35.86 |
| 9420 | 52 | $11,796 | $6,645 | 38.89% | 33.09 |
| 22481 | 80 | $27,507 | $9,279 | 41.67% | 32.17 |
| 4807 | 91 | $36,768 | $21,728 | 50.0% | 32.10 |

Genie recommended immediately freezing these five accounts.

**Why this answer is wrong:** Every account in the top 20 is a whale — a high-volume legitimate account, such as a payment aggregator or treasury account. The actual fraud consists of 1,000 accounts organized into 10 rings of 100 members each. None of them appear in this list. Genie sorted by inbound transfer count and raw risk score, which is exactly what the data was designed to fool. The 1,000 fraud ring members have moderate transfer volumes (15–30 each) and are completely invisible to this analysis.

The signals Genie used — high transfer count, disproportionate outflows, high-risk merchant percentage — are all whale characteristics, not fraud ring characteristics. Fraud ring members transact at ordinary volumes and visit a shared set of anchor merchants that is indistinguishable from background noise without graph structure.

---

## After: Genie With Graph Enrichment

This is what Genie returned after the GDS pipeline ran successfully and the gold tables were rebuilt with the corrected parameters.

**Question asked:** "Are there accounts acting as hubs of potentially fraudulent money movement networks?"

**Genie's answer:** Yes — 10 fraud rings identified, each containing exactly 100 confirmed fraudulent accounts.

| Community ID | Total Members | Fraud Members | Avg Risk Score | Avg Similarity Score |
|-------------|---------------|---------------|----------------|----------------------|
| 3515 | 109–127 | 100 | 1.2–1.5 | 0.18–0.22 |
| 8382 | 109–127 | 100 | 1.2–1.5 | 0.18–0.22 |
| 16873 | 109–127 | 100 | 1.2–1.5 | 0.18–0.22 |
| ... | ... | 100 | 1.2–1.5 | 0.18–0.22 |

Top hub accounts within rings (captain accounts):

| Account | Risk Score | Inbound | Outbound | Amount Received |
|---------|------------|---------|----------|----------------|
| 19903 | 2.58 | 26 | 26 | $622K |
| 12457 | 2.58 | 22 | 23 | $819K |
| 8554 | 2.55 | 28 | 20 | $394K |

Genie also correctly noted that the highest raw risk scores in the network (20–25) belong to legitimate high-volume accounts, not fraud ring members, and explained why: whale centrality comes from raw transfer volume while ring centrality comes from recursive topology.

**Why this answer is correct:** Genie used `community_id` to group accounts into rings, identified the 10 communities with 100 fraud members each, and then ranked hub accounts within those communities by `risk_score`. It also used `similarity_score` (0.18–0.22) to confirm coordinated merchant visit patterns across ring members. All three GDS features contributed to the answer.

---

## What Changed Between Before and After

**The data signal was not there before.** Two separate problems combined to make fraud invisible to the original GDS run:

1. **NodeSimilarity never completed.** The original notebook execution was interrupted silently, leaving only 28 `SIMILAR_TO` relationships instead of ~250,000. The `similarity_score` column on `gold_accounts` carried no meaningful signal.

2. **Generator parameters produced the wrong distribution.** With `WITHIN_RING_PROB=0.12` and `RING_ANCHOR_PREF=0.09` (from a `.env` override that silently took precedence over `config.py`), ring members shared almost no anchor merchants and had thin peer-to-peer structure. The within-ring Jaccard signal was 0.011, barely above the 0.0019 background noise. PageRank could not separate ring members from background accounts. The top 20 by `risk_score` contained zero fraud members.

After fixing the generator parameters (`WITHIN_RING_PROB=0.50`, `RING_ANCHOR_PREF=0.40`, `NUM_MERCHANTS=7500`) and re-running the full pipeline with the stale relationship cleanup in place, the within-ring Jaccard ratio rose from 6x to 191x, ring density ratio rose from 862x to 6,428x, and the GDS features produced real separation between fraud and normal accounts.

**The Genie space instructions were also wrong.** The original instructions told Genie to sort by `risk_score DESC` to find fraud, which surfaces whales. They also described the risk score range as 0–1 when the actual distribution runs from near-zero for normal accounts up to 25 for whales and 2–3 for ring captains. The corrected instructions tell Genie to filter by community structure first, then rank within communities — which is the pattern Genie used when it got it right.
