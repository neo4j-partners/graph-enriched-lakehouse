# Genie Test Protocol

This protocol validates Genie's query results at each stage of the demo against the known ground truth. Six checks are organized into two phases. The first phase — three checks before GDS enrichment — confirms that the structural gaps are present. The second phase — three checks after GDS enrichment — confirms that graph algorithms close each gap.

**Before-GDS checks pass when Genie fails.** A passing result in Checks 1–3 confirms that Genie cannot find the fraud signal without graph structure. If Genie returns ring-dominated results in any before-GDS check, the dataset has leaked tabular signal — re-run `verify_fraud_patterns.py` without `--genie-csv` to confirm the structural properties, then inspect the `.env` configuration.

Each check follows the same pattern: ask Genie the specified question, copy the returned table into the corresponding sample CSV, and run the verifier. The verifier reads `data/ground_truth.json` and reports PASS or FAIL with specific measurements.

---

## Setup

**1. Generate the data.**

From the `finance-genie/` directory:

```bash
cp setup/.env.sample setup/.env   # first time only
uv run setup/generate_data.py
```

This writes five CSV files and `data/ground_truth.json` to `./data/`. The JSON records the ten fraud rings, 200 whale accounts, and per-ring anchor merchants used by all six checks.

**2. Verify structural properties.**

```bash
uv run setup/verify_fraud_patterns.py
```

All four structural checks must PASS before running Genie. A structural failure means the dataset does not produce the graph signals the demo depends on.

**3. Load the tables into Databricks.**

From the `finance-genie/` directory:

```bash
export DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
./setup/upload_and_create_tables.sh
```

This drops any existing base tables, uploads the five CSVs to the Unity Catalog Volume, and recreates the Delta tables from scratch. Any GDS-enriched columns or tables written by earlier demo runs are cleared. Confirm the Genie Space dataset list points at the freshly created tables before proceeding.

---

## Phase 1 — Before GDS: Confirming the Structural Gaps

Run these three checks against the raw tables, before any GDS enrichment. The checks confirm that the three fraud signals — recursive centrality, community structure, and merchant-set overlap — are invisible to Genie's SQL-based analysis.

---

### Check 1: PageRank Gap — Raw Inbound Count Returns Whales

This check opens the centrality argument. Genie is asked a plain inbound-transfer ranking question with no fraud framing. It returns a raw count grouped by recipient, and the 200 whale accounts dominate that ranking.

The result looks like a clean answer — a ranked list of the most-transferred-to accounts — but it is measuring the wrong thing. Whale accounts receive transfers from many peripheral senders: accounts with few outbound links and no connections to other high-degree nodes. Fraud ring members receive transfers from other ring members who are themselves well-connected. A raw count cannot tell these apart, because it only asks how many, not who. The "who" question requires following the graph recursively, which is what PageRank does.

Ask Genie exactly:

> **"Which accounts receive the most inbound transfers? Show me the top 20 by total inbound transfer count."**

Genie should return a ranked list of account IDs. Copy the account IDs into the centrality sample CSV, one per row:

```
finance-genie/setup/genie_samples/genie_centrality.csv
```

The sample CSV is pre-populated with 10 known whale IDs for SEED=42. These pass out of the box and serve as a reference for what Genie should return before GDS enrichment.

Run the check from the `finance-genie/` directory:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_centrality.csv
```

**Pass criterion:** `whale_fraction >= 0.70`, `fraud_ring_count == 0`. A passing result confirms the gap is present.

The core problem with this result is not just that it missed the fraud — it is that there is no way to know it missed it. An analyst looking at the output sees a plausible-looking ranked list with no signal to distinguish a whale from a ring member. Precision, recall, and threshold sensitivity are all undefined: the query returns a fixed top-N slice with no score, no cutoff rationale, and no denominator. You cannot compute an F1 score because you have no way to evaluate either precision or recall from the output alone.

---

### Check 1.5: PageRank Getting Closer — 2-Hop Centrality Finds Mixed Signal

This check shows that better question framing gets Genie closer to the fraud signal — but lands in a different trap. Instead of finding only whales, it finds a mix of real fraud ring members and whales, which is in some ways worse: the result looks more like it is working, but the underlying accuracy problem is deeper than it appears.

Ask Genie:

> **"Find accounts where the people sending them money are also popular recipients. Show me accounts whose senders have above-average inbound transfer counts. I'm looking for fraudulent accounts."**

Genie will return a ranked list of accounts by number of "popular senders." The top results will be a mix of genuine fraud ring members from multiple rings and whale accounts. In a validated run with SEED=42, the top-11 accounts split roughly 5 fraud and 6 whales, and the hub accounts Genie flags as "circular payment hubs" skew toward real ring members from different rings.

The result surfaces real signal — ring members from rings 0, 3, 7, 8, and 9 appear in the top results. But three problems make it unactionable:

- **Precision degrades with depth.** The top-11 is ~45% fraud. The total flagged population in a typical run is around 4,500 accounts — in a dataset with only 1,000 ring members. Precision almost certainly deteriorates below the top results, but there is no way to know where.
- **Recall is unknown.** Of the 1,000 actual ring members, how many of the 4,500 flagged accounts are genuine? Without running every flagged account through ground truth, recall cannot be measured.
- **The threshold is arbitrary.** "Above-average inbound count" is a statistical cutoff with no principled basis. Tighten it and recall drops. Loosen it and precision drops further. There is no optimization target because there is no feedback signal.

> **Technical note:** What makes this unmeasurable is the absence of a labeled output. To compute an F1 score you need precision and recall, and to compute those you need to know which flagged accounts are true positives. The only way to get that is ground truth — which an analyst would not have in production. The result is a plausible-looking list that could be anywhere from 10% to 60% accurate, with no method to determine which.

There is no automated verifier for this check. To label the returned accounts manually against ground truth:

```python
import json
gt = json.load(open("data/ground_truth.json"))
ring_by_account = {a: r["ring_id"] for r in gt["rings"] for a in r["account_ids"]}
whales = set(gt["whale_account_ids"])

for acct_id in [13260, 5430, 24223]:  # replace with returned account IDs
    if acct_id in whales:
        print(f"{acct_id}: WHALE")
    elif acct_id in ring_by_account:
        print(f"{acct_id}: FRAUD — ring {ring_by_account[acct_id]}")
    else:
        print(f"{acct_id}: NORMAL")
```

**What PageRank corrects:** Ring members receive transfers from other ring members who are themselves high-scoring — the centrality compounds recursively through the ring topology. Whale accounts receive from peripheral senders whose own PageRank score is low, so their compounded score stays moderate despite the high raw inbound count. That separation shows up as a distributional break in the `risk_score` column. The analyst no longer needs ground truth to act: the score itself is the signal.

**Demo narrative value:** Check 1 shows Genie finding only whales with a clean-looking but wrong result. Check 1.5 shows Genie finding real fraud with better framing — but producing a result that is impossible to evaluate or act on. Check 4 shows PageRank producing a scored ranking where the separation is visible and the analyst has a basis for confidence without needing ground truth.

---

### Check 2: Louvain Gap — Pairs Without Communities

This check confirms the gap for community detection. The ten fraud rings each contain approximately 100 accounts with a dense internal transfer network — within-ring edge density is roughly 268x the background rate. Genie's best SQL approximation of community structure is a bidirectional pair query: find accounts that send money to each other and sort by mutual transfer count. That query finds ring members exchanging money, but it cannot see the community.

The distinction matters. SQL transitive closure — chaining bilateral pairs into connected components — would merge rings that share even one background cross-ring transfer. Louvain runs iterative global modularity optimization, drawing community boundaries that maximize within-group edge density relative to a statistical null model. That boundary computation requires graph-native iteration. SQL cannot replicate it.

Ask Genie exactly:

> **"Which groups of accounts are transferring money heavily among themselves? Try to identify clusters of accounts that predominantly send money to each other."**

Genie will likely return bilateral pairs — account A and account B with 3–4 mutual transfers. If prompted further, it may attempt to group pairs into clusters. In either case, the result is a set of small relationships, not a 100-account community.

Copy the returned pairs into:

```
finance-genie/setup/genie_samples/genie_community_pairs.csv
```

The CSV has two columns: `account_id_a` and `account_id_b`. If Genie returns a grouped result with a cluster label, record each (account, cluster) pair as a row with the cluster label in `account_id_b`.

Run the check:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_community_pairs.csv
```

**Pass criterion:** `largest_ring_footprint <= 20`. The verifier counts distinct ring accounts visible across all returned pairs, per ring. A passing result means Genie surfaced at most 20 accounts from any single ring — far short of the 100-member community. A failing result (footprint > 20) means Genie surfaced a large fraction of a ring through pairwise chaining, and the community-vs-pairs gap is narrower than intended.

**What to note when recording:** Even if most returned pairs are ring members (which is expected — ring members do exchange money), the key observation is that the pairs appear as isolated bilateral relationships. There is no way to tell from the result that these pairs belong to a 100-account group with a shared boundary distinct from adjacent rings. That is what Louvain reveals.

---

### Check 3: Node Similarity Gap — Raw Count Misses the Jaccard Signal

This check confirms the gap for node similarity. Each fraud ring has five anchor merchants drawn from the full pool of 2,500. Ring members visit these anchors at an elevated rate, giving them high within-ring Jaccard similarity. The overall high-risk merchant fraction for fraud accounts stays within 2.4 percentage points of normal accounts, so no merchant-tier column filter is useful.

Genie's best SQL approximation is a raw shared-merchant count: self-join on the transactions table, group by account pair, count distinct shared merchants. This produces absolute overlap without a denominator. High-volume normal accounts visiting hundreds of merchants accumulate more shared merchants in absolute count than ring members visiting approximately 30 merchants total with 4–5 anchors in common. Jaccard normalization corrects for visit volume; raw counts do not.

Ask Genie exactly:

> **"Which pairs of accounts have visited the most merchants in common? Show me the top 20 pairs by count of shared merchants."**

Genie should return account pairs with a shared merchant count. Copy the result into:

```
finance-genie/setup/genie_samples/genie_merchant_overlap.csv
```

The CSV has three columns: `account_id_a`, `account_id_b`, and `shared_merchant_count`.

Run the check:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_merchant_overlap.csv
```

**Pass criterion:** `same_ring_fraction < 0.30`. A passing result means fewer than 30% of the top-overlap pairs share a fraud ring, confirming that raw shared-merchant count is dominated by high-volume normal accounts rather than ring pairs.

If more than 30% of returned pairs are same-ring, high-volume normals may be underrepresented in the result, or the ring anchor merchants may be concentrated enough in absolute terms to dominate raw counts even without normalization. Re-run the structural verifier to confirm the Jaccard ratio is within target.

---

## What the Three Algorithms Add

The three gaps in Phase 1 correspond to three distinct structural limitations of SQL-based analysis.

**Louvain** is the strongest argument. Community detection requires iterative global modularity optimization — the algorithm updates every node's community assignment based on the full graph state, then repeats until the global modularity score converges. SQL can compute transitive closure (connected components), but connected components merge rings that share any cross-ring link. Louvain's modularity optimization keeps rings with distinct internal density profiles separated even when they share background noise edges. There is no equivalent SQL formulation.

**PageRank** compounds centrality across multiple hops. A bidirectional pair query finds accounts that exchange money directly. PageRank propagates that signal recursively — a ring member is central not just because their counterpart sends back, but because that counterpart is itself highly connected, and so on through the ring topology. Whale accounts receive from peripheral senders, so their recursive hub score is moderate despite the high raw count. Ring members receive from other high-PageRank ring members, so their score compounds. The distinction is invisible to any single-hop aggregate.

**Node Similarity** is the most tractable in SQL — a skilled analyst could write the Jaccard computation manually. The GDS advantage here is ergonomics and scale: Node Similarity scores every account pair in the bipartite account-merchant graph simultaneously, without requiring the analyst to know which pairs to examine. The demo's before/after contrast shows that the right metric (Jaccard vs. raw count) is the gap, not SQL's fundamental capability.

---

## Phase 2 — After GDS: Validating the Enrichment

Run these three checks after completing the GDS enrichment steps. The `accounts` table should have three new columns: `risk_score` (PageRank), `community_id` (Louvain), and `similarity_score` (Node Similarity).

---

### Check 4: PageRank Closes the Centrality Gap

After running PageRank in Neo4j Aura and writing `risk_score` back to the accounts table, ask Genie the parallel centrality question — now using the graph-enriched column. Ring members receive transfers from other ring members who are themselves high-scoring, compounding their PageRank score above the whale accounts.

Ask Genie exactly:

> **"Which accounts have the highest risk score?"**

Genie should return account IDs with their `risk_score` values. The `risk_score` column is required: the verifier uses it to distinguish this as a PageRank check rather than the before-GDS centrality check.

Copy the returned rows into:

```
finance-genie/setup/genie_samples/genie_pagerank.csv
```

The CSV has two columns: `account_id` and `risk_score`.

Run the check:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_pagerank.csv
```

**Pass criterion:** `ring_member_fraction >= 0.70`, `whale_count == 0`. A passing result confirms PageRank closed the centrality gap. Whale accounts, which received transfers from peripheral senders, score lower than ring members who received from other high-scoring ring nodes.

---

### Check 5: Louvain Community Purity

After Louvain assigns `community_id` to each account, ask Genie the parallel community question. Now that the community assignments are available as a column, Genie can answer the question correctly.

Ask Genie exactly:

> **"Show me accounts grouped by community ID, listing account IDs for each community."**

This is the same investigative question as Check 2, answered now with the GDS column. Where Check 2 returned bilateral pairs, this query returns full community membership — each community_id grouping the full ring.

Genie should return a table with `account_id` and `community_id` columns. Copy the full result into:

```
finance-genie/setup/genie_samples/genie_louvain.csv
```

Include accounts from at least two communities. A single community is insufficient to measure average purity across the result.

Run the check:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_louvain.csv
```

**Pass criterion:** `avg_community_purity >= 0.80`. A clean Louvain result maps each community to one fraud ring. The `per_community_purity` field in the report identifies which communities are impure. A community with mixed ring membership indicates Louvain merged two rings or the enrichment write-back to the Delta table was incomplete.

---

### Check 6: Node Similarity Surfaces Shared Anchor Merchants

After Node Similarity scores merchant-set overlap and writes `similarity_score` to the accounts table, ask Genie the parallel merchant-overlap question. Now that Jaccard scores are available as a column, Genie can rank pairs by normalized overlap rather than raw count.

Ask Genie exactly:

> **"Which pairs of accounts have the highest similarity score?"**

This is the same investigative question as Check 3, answered now with the GDS column. Where Check 3 returned pairs dominated by high-volume normal accounts (high raw count, low Jaccard), this query returns ring pairs sharing the same five anchor merchants.

Genie should return a table with `account_id_a`, `account_id_b`, and `similarity_score`. Copy the result into:

```
finance-genie/setup/genie_samples/genie_similarity.csv
```

Run the check:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_similarity.csv
```

**Pass criterion:** `same_ring_fraction >= 0.70`. To confirm why a passing pair scores high, look up that ring's anchor merchants in `ground_truth.json`:

```python
import json
gt = json.load(open("data/ground_truth.json"))
ring_by_account = {a: r["ring_id"] for r in gt["rings"] for a in r["account_ids"]}
anchors = {r["ring_id"]: r["anchor_merchants"] for r in gt["rings"]}

acct_a, acct_b = 4471, 9002  # replace with a returned pair
ring = ring_by_account.get(acct_a)
print(f"Ring {ring}")
for m in anchors.get(ring, []):
    print(f"  merchant {m['merchant_id']}: {m['category']} / {m['risk_tier']}")
```

---

## Running All Six Checks Together

After completing the full demo flow, validate all six CSVs in a single command:

```bash
uv run setup/verify_fraud_patterns.py \
  --genie-csv setup/genie_samples/genie_centrality.csv \
  --genie-csv setup/genie_samples/genie_community_pairs.csv \
  --genie-csv setup/genie_samples/genie_merchant_overlap.csv \
  --genie-csv setup/genie_samples/genie_pagerank.csv \
  --genie-csv setup/genie_samples/genie_louvain.csv \
  --genie-csv setup/genie_samples/genie_similarity.csv
```

The report prints a PASS or FAIL block for each check in before-GDS then after-GDS order. Recall that Checks 1–3 pass when Genie fails to find the fraud signal, and Checks 4–6 pass when Genie succeeds. The process exits with status 1 if any check fails.

---

## Ground Truth Reference

`data/ground_truth.json` records the full ring membership, whale list, and anchor merchants for the current seed. To label any account ID:

```python
import json
gt = json.load(open("data/ground_truth.json"))

ring_by_account = {a: r["ring_id"] for r in gt["rings"] for a in r["account_ids"]}
whales = set(gt["whale_account_ids"])

acct_id = 18762  # replace with the account to look up
if acct_id in whales:
    print(f"{acct_id}: WHALE")
elif acct_id in ring_by_account:
    print(f"{acct_id}: FRAUD — ring {ring_by_account[acct_id]}")
else:
    print(f"{acct_id}: NORMAL")
```

To inspect a ring's anchor merchants:

```python
ring_id = 3  # replace with the ring to inspect
ring = gt["rings"][ring_id]
print(f"Ring {ring_id}: {len(ring['account_ids'])} accounts")
for m in ring["anchor_merchants"]:
    print(f"  merchant {m['merchant_id']}: {m['category']} / {m['risk_tier']}")
```

`ground_truth.json` is regenerated each time `generate_data.py` runs. If the seed or any parameter in `setup/.env` changes, the ring and whale membership changes and all six sample CSVs must be re-populated with fresh Genie output.
