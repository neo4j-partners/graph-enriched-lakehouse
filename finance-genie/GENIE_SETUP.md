# Genie Space Setup — After GDS Enrichment

This guide covers the second Genie space: the one built over the GDS-enriched gold tables that closes the three gaps demonstrated in `genie_demos/`.

The first space (raw tables) shows Genie failing. This second space shows Genie succeeding — but only if it knows what `risk_score`, `community_id`, and `similarity_score` mean. Without explicit instructions, Genie treats them as generic numeric columns and generates queries that miss the point. The instructions in this guide fix that.

---

## Prerequisites

Both gold tables must exist before you create the space.

Run `feature_engineering/02_aura_gds_guide.ipynb` in the Neo4j Aura Workspace to compute PageRank, Louvain, and Node Similarity. Then run `feature_engineering/03_pull_gold_tables.ipynb` sections 6 and 7 to pull the enriched nodes from Neo4j and write the two gold tables to Delta.

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

Add all six tables to the space. The gold tables are the primary data sources; the base tables enable combined queries.

| Table | Catalog / Schema | Role |
|-------|-----------------|------|
| `gold_accounts` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account metadata plus the three GDS-computed features |
| `gold_account_similarity_pairs` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Jaccard similarity pairs from Node Similarity |
| `transactions` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account-to-merchant payment events |
| `account_links` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Account-to-account transfer edges |
| `merchants` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Merchant dimension |
| `account_labels` | `graph-enriched-lakehouse` / `graph-enriched-schema` | Fraud ground-truth labels |

---

## Instructions for the Genie Space

Paste the following into the **Instructions** field of the space. These instructions tell Genie what the GDS-computed columns mean and how to use them. Without them, Genie will not know to sort by `risk_score` for hub detection, group by `community_id` for ring detection, or query `gold_account_similarity_pairs` for merchant similarity.

---

```
This space is connected to a fraud detection dataset enriched with three graph features computed by Neo4j Graph Data Science. Understanding these features is required to answer fraud questions correctly.

## Graph Features

**gold_accounts.risk_score** (DOUBLE, range 0–1)
PageRank centrality computed on the account-to-account transfer graph. Accounts that receive transfers from other high-scoring accounts score higher. Fraud ring members score high because ring topology amplifies centrality recursively. High-volume normal accounts (whales) score moderate because their senders are peripheral low-centrality nodes.
- Use this column to rank accounts by fraud risk.
- Sort by risk_score DESC to surface fraud ring members above whale accounts.
- Do not use transfer count or inbound transfer amount as a proxy for this column. Volume and centrality are different things.

**gold_accounts.community_id** (BIGINT)
Louvain community label. Every account in the same fraud ring shares a single community_id. Accounts in different rings have different IDs. Normal accounts are assigned IDs for communities they naturally form but these communities are small and sparse compared to fraud rings.
- Use this column to identify fraud rings. GROUP BY community_id to surface ring-level structure.
- Do not attempt to detect rings using bilateral transfer pairs or recursive CTEs. The community_id column encodes ring membership directly.
- A community with 50 or more members and high internal transfer density is a fraud ring candidate.

**gold_accounts.similarity_score** (DOUBLE, range 0–1)
Node Similarity (Jaccard) score. Represents the maximum Jaccard similarity this account has with any other account based on shared merchant visits. Fraud ring members share a set of anchor merchants and score higher than high-volume normal accounts whose shared-merchant count is diluted by large merchant footprints.
- This column shows the per-account maximum similarity. For pairwise analysis, use gold_account_similarity_pairs instead.

## Pairwise Similarity Table

**gold_account_similarity_pairs** contains one row per account pair with columns account_id_a, account_id_b, and similarity_score. These pairs were computed using Jaccard normalization over shared merchant visits.
- For questions about which accounts share the most similar merchant patterns, query this table and sort by similarity_score DESC.
- Do not rank pairs by raw shared-merchant count. High-volume normal accounts accumulate many shared merchants by chance. Jaccard normalization corrects for merchant footprint size.
- Same-ring account pairs score around 0.09 Jaccard. High-volume normal pairs score around 0.08. The normalized score separates them; raw count does not.

## Answering Common Fraud Questions

"Which accounts have the highest fraud risk / are most central to the transfer network?"
→ SELECT account_id, risk_score FROM gold_accounts ORDER BY risk_score DESC LIMIT 20

"Which groups of accounts form suspicious communities / fraud rings?"
→ SELECT community_id, COUNT(*) AS member_count FROM gold_accounts GROUP BY community_id ORDER BY member_count DESC

"Which pairs of accounts share the most similar merchant visit patterns?"
→ SELECT account_id_a, account_id_b, similarity_score FROM gold_account_similarity_pairs ORDER BY similarity_score DESC LIMIT 20

"Show me the members of a specific fraud ring community"
→ SELECT * FROM gold_accounts WHERE community_id = <id> ORDER BY risk_score DESC

## Column Reference

gold_accounts: account_id, account_hash, account_type, region, balance, opened_date, holder_age, risk_score, community_id, similarity_score

gold_account_similarity_pairs: account_id_a, account_id_b, similarity_score

account_labels: account_id, is_fraud (use for validation only — this is ground truth not available in production)
```

---

## Connect the Notebook

Open `genie_demos/gds_enrichment_closes_gaps.ipynb` and find the configuration cell:

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
