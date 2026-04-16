# Admin Guide: Finance Genie

Genie can answer most questions a fraud analyst asks against raw Delta tables. It can sort accounts by inbound transfer volume, find account pairs with the most mutual transfers, and filter by merchant risk tier. What it cannot do is identify which account sits at the structural center of a money-flow network, which accounts form a closed transfer ring regardless of individual volume, or which accounts share the same small set of merchants in a pattern too sparse for any column filter to catch. Those three gaps are what this demo is designed to expose.

The walkthrough runs in two acts. In the first act, participants open a Genie space against the raw Delta tables and work through three fraud-investigation queries. Genie returns plausible but structurally incomplete answers. In the second act, the same tables are loaded into Neo4j Aura, PageRank, Louvain, and Node Similarity run as GDS algorithms, and the results write back to the lakehouse as three new columns on the accounts table. Genie then answers the same questions with full structural depth.

---

## The Dataset and Why It's Designed This Way

The synthetic dataset contains 25,000 accounts, 2,500 merchants, 250,000 transactions, and 40,000 peer-to-peer transfers. One thousand accounts (4%) are planted as fraud, distributed across ten rings of approximately 100 accounts each.

Every fraud pattern is calibrated to expose exactly one gap between Genie's column-based analysis and GDS graph analysis. Tabular signals, including transaction amounts, hours, and merchant tier fractions, are kept nearly identical between fraud and normal accounts. The signal lives in structure.

### Whale Accounts Hide the Ring from Raw Sorting (PageRank)

Two hundred normal accounts are designated as P2P "whales," modeled as payment aggregators with high bidirectional transfer volume. They receive 20% of all transfer links (WHALE_INBOUND), giving them raw inbound counts of roughly 40 each (measured: 40.6 average). They also originate 20% of all transfer links (WHALE_OUTBOUND). Each whale sends exclusively to a pre-assigned pool of ~30 recurring plain-normal-account recipients (WHALE_FIXED_OUTBOUND, WHALE_RECIPIENT_POOL_SIZE), matching the consistent-counterparty pattern of a real payment aggregator: the same vendors, employees, and refund recipients appearing repeatedly across the 90-day window. Fraud ring members receive approximately 6 links each from within-ring transfers and send at low background rates.

Ring members represent a layering pattern: funds enter the ring through external deposits and cycle repeatedly among members before exiting, obscuring origin across dozens of bilateral hops. No individual transfer amount, merchant category, or account balance distinguishes these accounts in isolation. The structural signal is that ring members receive transfers from other ring members — accounts that are themselves highly connected. Genie should be asking not which accounts receive the most transfers, but which accounts receive from other highly-connected accounts. PageRank encodes that distinction; a column sort does not.

```
Whale topology                          Ring topology

  p ─┐      ┌─→ q                    ┌──→ B ──→ C ─┐
  p ─┤      ├─→ q                    │               ↓
  p ─┼─→ WHALE                       A               D
  p ─┤      ├─→ q                    ↑               │
  p ─┘      └─→ q                    └─ F ←─ E ←────┘

  p = peripheral sender (low PR)     each node sends to and receives from
  q = fixed-pool recipient (low PR)  other ring members; PageRank compounds
  WHALE: high volume both ways,
  but all neighbors are peripheral → moderate PageRank
```

When Genie sorts accounts by inbound transfer count, the top 20 results are all whales. None are fraud ring members. Whales attract transfers from low-degree peripheral accounts, so their recursive hub score (PageRank) is moderate despite the high raw count. Ring members receive from other ring members who also have elevated connectivity. Their PageRank compounds through the ring topology.

The demo gap: Genie names whales. PageRank names the ring.

### Ten Rings Produce a 268x Density Signal (Louvain)

The ten fraud rings are partitioned before any links are generated. Within-ring P2P links account for 30% of all 40,000 transfers, distributed randomly across ring pairs rather than concentrated on specific bilateral relationships. This keeps individual pair counts at 1–4 transfers, low enough that Genie's top bilateral pairs look like isolated suspicious activity rather than a ring.

Ring members are fraudulent because their collective transfer behavior forms an anomalously dense subgraph: 30% of all transfers circulate within 4% of accounts. No individual transaction or bilateral pair looks suspicious in isolation. The signal emerges only when all transfer relationships for a group of accounts are evaluated together. Genie should be asking not which two accounts have the most mutual transfers, but which groups of accounts transfer among themselves at a rate far above background. Louvain detects that internal density; pair-level queries surface only isolated fragments of the ring.

```
What Genie sees                         What Louvain sees

  A ─── B                               ┌─────────────────┐
                                         │  A ─ B ─ C ─ D  │
        C ─── D                         │  |   |   |   |  │
                                         │  E ─ F ─ G ─ H  │
              E ─── F                   │  |   |   |   |  │
                                         │  I ─ J ─ K ─ L  │
  isolated suspicious pairs             └─────────────────┘
  ~30 accounts flagged                   dense community, ~100 accounts
                                         268x internal vs background density
```

Within-ring edge density is 0.048. Between-account background density is 0.000056. The ratio is approximately 860x. Louvain resolves this into ten communities of ~100 accounts each. Genie sees isolated suspicious pairs involving a fraction of ring members. Louvain finds all 1,000.

The demo gap: Genie finds hints of fraud at the pair level. Louvain finds the ring.

### Anchor Merchants Create Jaccard Signal Without a Column Signal (Node Similarity)

Each ring is assigned five specific anchor merchants, sampled from the full merchant pool rather than exclusively from high-risk merchants. Fraud accounts transact at a ring anchor 18% of the time. Because the anchors are drawn from all 2,500 merchants, the overall high-risk merchant fraction for fraud accounts (23.4%) stays within 2.4 percentage points of normal accounts (21.0%), not enough for a merchant-tier column filter to be useful.

Ring members are fraudulent because they share an identical behavioral fingerprint: each member's transaction history includes the same five anchor merchants, regardless of merchant risk tier. The distinguishing factor is merchant identity, not merchant category. Genie should be asking not which two accounts share a merchant, but which accounts share a high fraction of the same merchant set. Jaccard similarity captures that fraction as shared merchants divided by total distinct merchants across both accounts; a raw shared-merchant count cannot, because across 2,500 merchants almost any two accounts share at least one by chance.

```
What Genie sees                         What Node Similarity sees

 A ─── M_42                             A ──┬── anchor_7
 B ─── M_42   (1 shared)                B ──┘
                                         A ──┬── anchor_19
 C ─── M_87                             B ──┘
 D ─── M_87   (1 shared)                A ──┬── anchor_33
                                         B ──┘
                                         A ──┬── anchor_51
 isolated overlapping pairs              B ──┘
 Jaccard ≈ 0.01                         A ──┬── anchor_76
                                         B ──┘

                                         5 of 2,500 merchants shared
                                         Jaccard: high; same fingerprint
```

The structural signal is that ring members share the same specific anchor merchants. Average Jaccard similarity within a ring is approximately 6x higher than the fraud-to-normal cross rate (measured: within_ring_jaccard 0.011 vs cross_rate 0.0019). GDS Node Similarity scores every account pair by merchant-set overlap simultaneously; Genie can only count raw shared merchants, where nearly all pairs share at most one.

The demo gap: Genie finds account pairs with one shared merchant. Node Similarity scores the full bipartite overlap and surfaces the ring.

---

## Notebooks

| # | File | Runs In | Purpose |
|---|------|---------|---------|
| 00 | `00_required_setup.ipynb` | Databricks | Widget-based setup: creates a per-user Unity Catalog, generates the synthetic dataset as Delta tables, stores Neo4j credentials as Databricks secrets, and verifies the Aura connection. |
| 01 | `01_neo4j_ingest.ipynb` | Databricks | Pushes the operational Delta tables (`accounts`, `merchants`, `transactions`, `account_links`) into Neo4j Aura as a typed property graph via the Neo4j Spark Connector. |
| 02 | `02_aura_gds_guide.ipynb` | Neo4j Aura Workspace | Cypher and GDS commands to project the graph, run PageRank / Louvain / Node Similarity, and write `risk_score`, `community_id`, and `similarity_score` back as Account node properties. Also available as [`aura_gds_guide.md`](./aura_gds_guide.md). |
| 03 | `03_pull_and_model.ipynb` | Databricks | Reads enriched Account nodes back via the Spark Connector, registers graph features in Unity Catalog Feature Store, trains a baseline vs graph-augmented `GradientBoostingClassifier`, and compares AUC / F1 / ROC curves with an estimated dollar impact from additional fraud caught. |

---

## Admin Quick Start

Run these steps before the workshop. Participants do not need to follow this section.

### 1. Prerequisites

- Databricks workspace admin access (Unity Catalog enabled)
- Dedicated compute cluster with the Neo4j Spark Connector installed:
  - Maven: `org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3`
  - Runtime: 13.3 LTS or higher
- Neo4j Aura instance with GDS enabled (AuraDS or Aura Plugin)
- `uv` installed locally (`pip install uv` or via [uv docs](https://docs.astral.sh/uv/))

### 2. Generate and Validate the Dataset

Run the data generator locally before the workshop to confirm the fraud patterns are intact and the CSVs look as expected:

```bash
cd finance-genie
```

```bash
uv run setup/generate_data.py --output ./data/
```

This writes four CSV files to `./data/` with no Databricks dependency: only `pandas` and Python 3.9+ are required. Inspect the outputs to confirm:

- `accounts.csv`: 25,000 rows, 1,000 marked `is_fraud = True`
- `merchants.csv`: 2,500 rows across eight categories and three risk tiers
- `transactions.csv`: 250,000 rows, fraud transactions at ~10,100 (~4%)
- `account_links.csv`: 40,000 rows, 30% concentrated within the ten fraud rings

By default (`WHALE_FIXED_OUTBOUND=true`), each of the 200 whale accounts sends outbound transfers only to its own pre-assigned pool of 30 recurring recipients (`WHALE_RECIPIENT_POOL_SIZE=30`). Recipients are plain normal accounts, so they stay low-degree and do not inflate the whale's PageRank. To switch to random outbound destinations instead, set `WHALE_FIXED_OUTBOUND=false` in `setup/.env`. Both modes preserve the PageRank separation between whales and ring members; the fixed-pool mode adds the realistic consistent-counterparty pattern of a payment aggregator.

The CSVs are for local inspection only. The setup notebook generates the Delta tables independently when each participant runs it.

### 3. Prepare the Workspace

Before participants arrive:

- Confirm the dedicated cluster has the Neo4j Spark Connector Maven library attached and is running on Runtime 13.3 LTS or higher
- Confirm participants have `CREATE CATALOG` permission in the Unity Catalog metastore, or pre-create a catalog they can write to
- Share the Neo4j Aura connection details (URI, username, password) with participants. Each participant enters these into the setup notebook widgets.

### 4. Verify Genie Answers Against the Ground Truth

`generate_data.py` writes `data/ground_truth.json` alongside the CSVs. The file records the ten fraud rings as lists of account IDs, the 200 whale accounts that dominate raw inbound transfer counts, and the five anchor merchants assigned to each ring. Each anchor entry includes its category and risk tier, so nothing requires a CSV lookup.

During the workshop, Genie returns account IDs at three points in the demo. Each point has a specific expected result:

| Demo stage | Genie query | Expected result |
|---|---|---|
| Before GDS | Most central accounts by transfer volume | All returned IDs appear in `whale_account_ids`; none in any ring |
| After PageRank | Accounts with highest `risk_score` | All returned IDs appear in a ring's `account_ids`; whales drop out |
| After Louvain | Accounts grouped by `community_id` | Each community maps cleanly to one ring's `account_ids` |
| After Node Similarity | Account pairs with highest `similarity_score` | Both accounts in each pair belong to the same ring and share that ring's `anchor_merchants` |

The following snippet loads the ground truth and builds lookup structures for each check:

```python
import json

with open("data/ground_truth.json") as f:
    gt = json.load(f)

whales = set(gt["whale_account_ids"])
ring_by_account = {
    acct: r["ring_id"]
    for r in gt["rings"]
    for acct in r["account_ids"]
}
anchors_by_ring = {r["ring_id"]: r["anchor_merchants"] for r in gt["rings"]}
```

**Before GDS: whale check.** Paste the account IDs Genie returned into `returned`, then run:

```python
returned = [18762, 11147, 3801, 15940, 7698]  # replace with Genie's output

print("Whales (expected — all):", [a for a in returned if a in whales])
print("Ring members (expected — none):", [(a, ring_by_account[a]) for a in returned if a in ring_by_account])
```

A passing result shows every ID in the whale list and an empty ring list.

**After PageRank: ring membership check.** The same query should now return fraud ring members:

```python
print("Ring members (expected — all):", [(a, ring_by_account[a]) for a in returned if a in ring_by_account])
print("Whales (expected — none):", [a for a in returned if a in whales])
```

**After Louvain: community purity check.** For each Genie community, confirm all members share a single ring:

```python
community_members = [24, 819, 1203, 4471, 9002]  # replace with one community's account IDs

rings_represented = set(ring_by_account.get(a) for a in community_members if a in ring_by_account)
print("Rings in this community (expected — exactly one):", rings_represented)
```

A passing result returns a single `ring_id`. Multiple values indicate Louvain merged two rings or the enrichment did not write back cleanly.

**After Node Similarity: anchor merchant check.** For a high-similarity account pair, confirm both accounts belong to the same ring and look up that ring's shared anchors:

```python
acct_a, acct_b = 4471, 9002  # replace with a high-similarity pair from Genie

ring_a = ring_by_account.get(acct_a)
ring_b = ring_by_account.get(acct_b)
print(f"Account {acct_a} → ring {ring_a}")
print(f"Account {acct_b} → ring {ring_b}")

if ring_a == ring_b and ring_a is not None:
    print("Shared anchor merchants:", anchors_by_ring[ring_a])
else:
    print("Accounts belong to different rings — similarity is noise, not ring structure")
```
