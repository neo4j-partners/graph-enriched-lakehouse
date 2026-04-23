# GDS Algorithms in Neo4j Aura

**This is a reference guide.** Run these commands in the **Neo4j Aura Workspace**
(Query tab), not in Databricks. It is a standalone alternative to
`03_gds_enrichment.ipynb` for readers who prefer to follow along outside a
Databricks notebook.

After running `02_neo4j_ingest`, switch to Aura and execute the steps below.
When finished, return to Databricks and run `04_pull_gold_tables`.

## What We're Computing

| Algorithm | Property Written | Fraud Signal |
|-----------|-----------------|--------------|
| **PageRank** | `Account.risk_score` | Central accounts in money-flow networks |
| **Louvain** | `Account.community_id` | Tightly connected clusters (fraud rings) |
| **Node Similarity** | `Account.similarity_score` | Accounts sharing the same merchants |

---

## How the Fraud Signal Gets In

Each algorithm reads a different part of the synthetic graph. The signal was planted at data-generation time and the algorithms recover it without ever seeing the fraud labels.

**PageRank and Louvain — signal source: within-ring transfers**

Each fraud ring has 100 accounts. At generation time, `WITHIN_RING_PROB` of all P2P transfers are forced to stay inside a ring: ring members send money to other ring members at a much higher rate than background accounts do. This creates a dense internal `TRANSFERRED_TO` subgraph for each ring.

- **Louvain** sees that density as a tight community and assigns all members the same `community_id`.
- **PageRank** sees ring members recursively passing centrality to each other. Because the senders are themselves well-connected ring members, the centrality compounds — ring members score higher than background accounts even though their raw transfer counts are moderate.

Both algorithms project only Account nodes and `TRANSFERRED_TO` relationships. Merchant data plays no role.

**NodeSimilarity — signal source: anchor merchants**

Each fraud ring is assigned 4 anchor merchants at generation time. Ring members direct `RING_ANCHOR_PREF` of their transactions toward those specific 4 merchants. Normal accounts visit merchants uniformly at random.

The result: ring members share a distinctive set of merchants. NodeSimilarity projects the bipartite Account–Merchant graph (`TRANSACTED_WITH` relationships) and computes Jaccard similarity over shared merchant sets. Two accounts that visit the same 4 anchor merchants out of a pool of thousands score high; two accounts whose shared merchants are explained by random volume score low.

The data flow for NodeSimilarity is:
```
anchor merchants assigned at generation
    → ring members preferentially TRANSACTED_WITH those merchants
    → bipartite Account–Merchant projection
    → NodeSimilarity computes Jaccard over shared merchant sets
    → similarity_score written to Account nodes
```

All three GDS algorithms operate purely on graph structure.

---

## Step 1: Verify and Explore the Graph

Before projecting anything, make sure the ingest landed and get a feel for the
shape of the data.

### 1a. Node and relationship counts

```cypher
MATCH (a:Account) WITH count(a) AS accounts
MATCH (m:Merchant) WITH accounts, count(m) AS merchants
MATCH ()-[t:TRANSACTED_WITH]->() WITH accounts, merchants, count(t) AS txns
MATCH ()-[p:TRANSFERRED_TO]->() WITH accounts, merchants, txns, count(p) AS p2p
RETURN accounts, merchants, txns, p2p
```

**Expected:** ~25,000 accounts, ~7,500 merchants, ~250,000 transactions, ~300,000 transfers.

### 1b. Account breakdown by transfer activity

```cypher
MATCH (a:Account)
OPTIONAL MATCH (a)-[:TRANSFERRED_TO]-()
WITH a, count(*) AS degree
RETURN a.account_type AS account_type,
       count(a) AS account_count,
       round(avg(a.balance), 2) AS avg_balance,
       round(avg(degree), 1) AS avg_degree,
       max(degree) AS max_degree
ORDER BY account_count DESC
```

**What to look for:** transfer degree is fairly uniform across account types.
No single column separates high-risk accounts from low-risk ones — that is the
whole point. The separation lives in graph structure, not in tabular attributes.

### 1c. Account breakdown by balance tier

```cypher
MATCH (a:Account)
WITH a,
     CASE WHEN a.balance < 10000 THEN 'low'
          WHEN a.balance < 100000 THEN 'mid'
          ELSE 'high' END AS balance_tier
RETURN balance_tier,
       count(a) AS accounts,
       round(avg(a.balance), 2) AS avg_balance,
       min(a.holder_age) AS min_age,
       max(a.holder_age) AS max_age
ORDER BY accounts DESC
```

**What to look for:** balance tiers and age ranges overlap heavily across all
groups. A column filter cannot isolate the fraud rings.

### 1d. Sample the subgraph around an account

```cypher
MATCH (a:Account)
WHERE (a)-[:TRANSFERRED_TO]-()
WITH a LIMIT 1
OPTIONAL MATCH (a)-[t:TRANSACTED_WITH]->(m:Merchant)
OPTIONAL MATCH (a)-[p:TRANSFERRED_TO]->(b:Account)
RETURN a, t, m, p, b
```

**What to look for:** the account connects to merchants across various
categories and has at least one `TRANSFERRED_TO` edge to another account.
Good visual primer before running the algorithms.

---

## Step 2: Project the Account Transfer Graph

GDS algorithms run on an **in-memory graph projection**, not directly on the database.
This projects only Account nodes and `TRANSFERRED_TO` relationships: the peer-to-peer
money-flow graph where fraud rings live.

```cypher
CALL gds.graph.drop('account_transfers', false) YIELD graphName;
CALL gds.graph.project(
  'account_transfers',
  'Account',
  {TRANSFERRED_TO: {orientation: 'UNDIRECTED'}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
```

**Expected:** ~25,000 nodes, ~300,000 relationships.

---

## Step 3: Run PageRank (Risk Centrality)

PageRank measures how "central" an account is in the transfer network.
Accounts that receive money from many well-connected accounts score higher.
That is exactly how money-mule networks operate.

```cypher
CALL gds.pageRank.write(
  'account_transfers',
  {
    maxIterations: 20,
    dampingFactor: 0.85,
    writeProperty: 'risk_score'
  }
)
YIELD nodePropertiesWritten, ranIterations, didConverge
RETURN nodePropertiesWritten, ranIterations, didConverge
```

**Verify: top 10 by PageRank:**

```cypher
MATCH (a:Account)
WHERE a.risk_score IS NOT NULL
RETURN a.account_id AS id,
       round(a.risk_score, 6) AS pagerank
ORDER BY a.risk_score DESC
LIMIT 10
```

These top accounts are the most central nodes in the transfer network. Cross-reference the IDs against `account_labels` in Databricks after running the full pipeline to verify the fraud signal.

---

## Step 4: Run Louvain Community Detection (Fraud Rings)

Louvain finds clusters of densely connected accounts. In a legitimate network,
communities are large and diffuse. Fraud rings form **small, tight clusters**
with heavy internal transfers.

```cypher
CALL gds.louvain.write(
  'account_transfers',
  {
    writeProperty: 'community_id'
  }
)
YIELD communityCount, modularity, nodePropertiesWritten
RETURN communityCount, modularity, nodePropertiesWritten
```

**Verify: community size distribution:**

```cypher
MATCH (a:Account)
WHERE a.community_id IS NOT NULL
RETURN a.community_id AS community, count(*) AS size
ORDER BY size DESC
LIMIT 15
```

**Visualise a small, dense community (likely a fraud ring):**

```cypher
MATCH (a:Account)
WHERE a.community_id IS NOT NULL
WITH a.community_id AS community, count(*) AS size
ORDER BY size ASC LIMIT 1
WITH community
MATCH (m:Account {community_id: community})-[r:TRANSFERRED_TO]-(other:Account {community_id: community})
RETURN m, r, other
```

**How this query works:**

The query runs in two stages separated by the intermediate `WITH community`.

*Stage 1 — find the smallest community:*
- `MATCH (a:Account) WHERE a.community_id IS NOT NULL` collects every account Louvain has labelled.
- `WITH a.community_id AS community, count(*) AS size` groups by community and counts members.
- `ORDER BY size ASC LIMIT 1` picks the single smallest community. Small is the tell: the background population forms one large community of thousands of accounts; fraud rings form tight clusters of ~100.
- The second `WITH community` discards `size` and carries only the community ID into stage 2, which is what makes the `LIMIT 1` stick — without it the next `MATCH` would re-expand and lose the single-community constraint.

*Stage 2 — retrieve the internal transfer subgraph:*
- `MATCH (m:Account {community_id: community})-[r:TRANSFERRED_TO]-(other:Account {community_id: community})` finds every `TRANSFERRED_TO` relationship where **both** endpoints belong to that community. The undirected `-` (rather than `->`) returns edges in either direction, so the full internal transfer graph is captured.
- `RETURN m, r, other` hands nodes and relationships to the Aura visual renderer, which draws them as a graph.

The result is a graph panel showing only the accounts inside the ring and the transfers between them. A fraud ring looks like a dense hairball; a random slice of background accounts looks like a sparse tree.

---

## Step 5: Drop the Transfer Graph Projection

Clean up before creating the next projection.

```cypher
CALL gds.graph.drop('account_transfers')
YIELD graphName
RETURN graphName
```

---

## Step 6: Project the Bipartite Graph (Account → Merchant)

Node Similarity needs the bipartite graph: which accounts transact
with which merchants.

```cypher
CALL gds.graph.project(
  'account_merchants',
  ['Account', 'Merchant'],
  {TRANSACTED_WITH: {orientation: 'NATURAL'}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
```

---

## Step 7: Run Node Similarity (Shared Merchant Patterns)

Two accounts are similar if they transact with the **same merchants**.
Fraud accounts typically share a small set of high-risk merchants.

```cypher
CALL gds.nodeSimilarity.write(
  'account_merchants',
  {
    similarityMetric: 'JACCARD',
    topK: 5,
    similarityCutoff: 0.3,
    writeRelationshipType: 'SIMILAR_TO',
    writeProperty: 'similarity_score'
  }
)
YIELD nodesCompared, relationshipsWritten
RETURN nodesCompared, relationshipsWritten
```

**Verify: most similar account pairs:**

```cypher
MATCH (a:Account)-[s:SIMILAR_TO]-(b:Account)
WHERE a.account_id < b.account_id
RETURN a.account_id AS account_a,
       b.account_id AS account_b,
       round(s.similarity_score, 3) AS similarity
ORDER BY s.similarity_score DESC
LIMIT 10
```

---

## Step 8: Aggregate Max Similarity per Account

For each account, store its **highest similarity score** as a node property.
This makes it easy to read back as a single feature column in Databricks.

```cypher
MATCH (a:Account)
OPTIONAL MATCH (a)-[s:SIMILAR_TO]-()
WITH a, COALESCE(MAX(s.similarity_score), 0.0) AS max_sim
SET a.similarity_score = max_sim
RETURN count(a) AS accounts_updated
```

---

## Step 9: Drop the Bipartite Graph Projection

```cypher
CALL gds.graph.drop('account_merchants')
YIELD graphName
RETURN graphName
```

---

## Step 10: Final Verification, All Features Written

Confirm all three properties exist on Account nodes:

```cypher
MATCH (a:Account)
WHERE a.risk_score IS NOT NULL
  AND a.community_id IS NOT NULL
  AND a.similarity_score IS NOT NULL
RETURN count(a) AS accounts_with_all_features
```

**Feature distribution by community size:**

```cypher
MATCH (a:Account)
WHERE a.risk_score IS NOT NULL
  AND a.community_id IS NOT NULL
  AND a.similarity_score IS NOT NULL
WITH a.community_id AS community,
     count(a) AS size,
     round(avg(a.risk_score), 6) AS avg_pagerank,
     round(avg(a.similarity_score), 4) AS avg_similarity
RETURN CASE WHEN size <= 150 THEN 'small (ring candidate)' ELSE 'large (background)' END AS community_type,
       count(community) AS num_communities,
       round(avg(avg_pagerank), 6) AS avg_pagerank,
       round(avg(avg_similarity), 4) AS avg_similarity
ORDER BY community_type
```

Small communities (fraud rings, ~100 accounts each) should show higher average
PageRank and similarity scores than the large background community. That
separation is the signal.

---

## Step 11: Fraud Detection Queries in Pure Cypher

Before handing the features back to Databricks, it is worth seeing the payoff
in Cypher alone. These two queries combine the GDS-written properties with
the raw graph to surface fraud patterns directly.

### 11a. Identify Ring Members

A fraud ring is a Louvain community where multiple accounts both send *and*
receive money within the same community. Accounts that only send or only
receive are peripheral; accounts on both sides of a transfer are core ring
participants. The query collects senders and receivers per community, then
intersects them. Any account in both lists is a confirmed bidirectional
participant. Communities with three or more such accounts are coordinated
rings, not coincidence.

```cypher
MATCH (s:Account)-[:TRANSFERRED_TO]->(r:Account)
WHERE s.community_id IS NOT NULL
  AND s.community_id = r.community_id
WITH s.community_id AS community,
     collect(DISTINCT s.account_id) AS senders,
     collect(DISTINCT r.account_id) AS receivers
WITH community,
     [x IN senders WHERE x IN receivers] AS ring_members
WHERE size(ring_members) >= 3
RETURN community,
       ring_members,
       size(ring_members) AS ring_size
ORDER BY ring_size DESC
```

**What to look for:** small communities (tight clusters) with `ring_size >= 3`.
The Louvain + bidirectional intersection combo finds rings without needing
labels. Validate precision by checking the returned account IDs against
`account_labels` in Databricks after completing the pipeline.

### 11b. Off-Hours Transaction Detection

Fraud accounts in this dataset skew slightly toward off-hours activity.
Flagging accounts with three or more transactions between midnight and 5am,
then joining the already-written `risk_score` and `community_id`, gives a
single ranked list that combines structural (graph) and behavioural (time-of-day)
signal.

```cypher
MATCH (a:Account)-[t:TRANSACTED_WITH]->(m:Merchant)
WHERE t.txn_hour >= 0 AND t.txn_hour < 6
WITH a,
     count(t)                        AS off_hours_count,
     round(avg(t.amount), 2)         AS avg_amount,
     round(sum(t.amount), 2)         AS total_amount,
     collect(DISTINCT m.merchant_id) AS merchants_used
WHERE off_hours_count >= 3
RETURN a.account_id         AS account_id,
       a.risk_score          AS risk_score,
       a.community_id        AS community_id,
       off_hours_count,
       avg_amount,
       total_amount,
       size(merchants_used)  AS distinct_merchants
ORDER BY off_hours_count DESC
LIMIT 25
```

**What to look for:** accounts with high `off_hours_count` that *also* have
a high `risk_score` and share a `community_id` with other flagged accounts.
Those are the strongest fraud candidates: three independent signals pointing
at the same account.

---

## Done in Aura

The graph now has three GDS-computed properties on every Account node:

- `risk_score`: centrality in the transfer network
- `community_id`: Louvain cluster assignment
- `similarity_score`: highest Jaccard similarity to any other account

**Next →** Return to Databricks and run `04_pull_gold_tables` to read these
features back into Unity Catalog as the three Gold tables the AFTER Genie
space queries.
