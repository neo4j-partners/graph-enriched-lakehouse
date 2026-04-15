# GDS Algorithms in Neo4j Aura

**This is a reference guide.** Run these commands in the **Neo4j Aura Workspace**
(Query tab) — not in Databricks. It is a plain-markdown alternative to
[`02_aura_gds_guide.py`](./02_aura_gds_guide.py) for readers who prefer to follow
along outside a Databricks notebook.

After running `01_neo4j_ingest`, switch to Aura and execute the steps below.
When finished, return to Databricks and run `03_pull_and_model`.

## What We're Computing

| Algorithm | Property Written | Fraud Signal |
|-----------|-----------------|--------------|
| **PageRank** | `Account.risk_score` | Central accounts in money-flow networks |
| **Louvain** | `Account.community_id` | Tightly connected clusters (fraud rings) |
| **Node Similarity** | `Account.similarity_score` | Accounts sharing the same merchants |

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

**Expected:** ~5,000 accounts, ~500 merchants, ~50,000 transactions, ~8,000 transfers.

### 1b. Fraud vs legitimate account breakdown

```cypher
MATCH (a:Account)
RETURN a.is_fraud             AS is_fraud,
       count(a)                AS account_count,
       round(avg(a.balance), 2) AS avg_balance,
       min(a.holder_age)        AS min_age,
       max(a.holder_age)        AS max_age
ORDER BY is_fraud DESC
```

**What to look for:** ~200 fraud accounts (4%) vs ~4,800 legitimate accounts.
Balances and holder-age ranges should overlap heavily — that's the whole point
of the dataset. The graph is where the separation lives.

### 1c. Merchant risk-tier distribution

```cypher
MATCH (m:Merchant)
RETURN m.risk_tier     AS risk_tier,
       m.category       AS category,
       count(m)         AS merchant_count
ORDER BY risk_tier, merchant_count DESC
```

**What to look for:** `crypto` and `gaming` categories skew heavily toward
`risk_tier = high` — these are the merchants fraud accounts preferentially
transact with.

### 1d. Sample the subgraph around a fraud account

```cypher
MATCH (a:Account {is_fraud: true})
WITH a LIMIT 1
OPTIONAL MATCH (a)-[t:TRANSACTED_WITH]->(m:Merchant)
OPTIONAL MATCH (a)-[p:TRANSFERRED_TO]->(b:Account)
RETURN a, t, m, p, b
```

**What to look for:** the fraud account should connect to several `risk_tier = high`
merchants and have at least one outgoing `TRANSFERRED_TO` edge to another
account. Good visual primer before running the algorithms.

---

## Step 2: Project the Account Transfer Graph

GDS algorithms run on an **in-memory graph projection**, not directly on the database.
This projects only Account nodes and `TRANSFERRED_TO` relationships — the peer-to-peer
money-flow graph where fraud rings live.

```cypher
CALL gds.graph.project(
  'account_transfers',
  'Account',
  {TRANSFERRED_TO: {orientation: 'UNDIRECTED'}}
)
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount
```

**Expected:** ~5,000 nodes, ~8,000 relationships.

---

## Step 3: Run PageRank (Risk Centrality)

PageRank measures how "central" an account is in the transfer network.
Accounts that receive money from many well-connected accounts score higher —
exactly how money-mule networks operate.

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

**Verify — top 10 by PageRank:**

```cypher
MATCH (a:Account)
WHERE a.risk_score IS NOT NULL
RETURN a.account_id AS id,
       a.is_fraud AS fraud,
       round(a.risk_score, 6) AS pagerank
ORDER BY a.risk_score DESC
LIMIT 10
```

Look for fraud accounts appearing in the top results — that's the signal.

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

**Verify — community size distribution:**

```cypher
MATCH (a:Account)
WHERE a.community_id IS NOT NULL
RETURN a.community_id AS community, count(*) AS size
ORDER BY size DESC
LIMIT 15
```

**Visualise a fraud-heavy community:**

```cypher
MATCH (a:Account)
WHERE a.community_id IS NOT NULL AND a.is_fraud = true
WITH a.community_id AS community, count(*) AS fraud_count
ORDER BY fraud_count DESC LIMIT 1
WITH community
MATCH (m:Account {community_id: community})-[r:TRANSFERRED_TO]-(other:Account {community_id: community})
RETURN m, r, other
```

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

**Verify — most similar account pairs:**

```cypher
MATCH (a:Account)-[s:SIMILAR_TO]-(b:Account)
WHERE a.account_id < b.account_id
RETURN a.account_id AS account_a,
       b.account_id AS account_b,
       round(s.similarity_score, 3) AS similarity,
       a.is_fraud AS a_fraud,
       b.is_fraud AS b_fraud
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

## Step 10: Final Verification — All Features Written

Confirm all three properties exist on Account nodes:

```cypher
MATCH (a:Account)
WHERE a.risk_score IS NOT NULL
  AND a.community_id IS NOT NULL
  AND a.similarity_score IS NOT NULL
RETURN count(a) AS accounts_with_all_features
```

**Fraud vs legitimate comparison:**

```cypher
MATCH (a:Account)
RETURN a.is_fraud AS is_fraud,
       count(a) AS count,
       round(avg(a.risk_score), 6) AS avg_pagerank,
       round(avg(a.similarity_score), 4) AS avg_similarity,
       count(DISTINCT a.community_id) AS num_communities
ORDER BY a.is_fraud
```

You should see clear separation between fraud and legitimate accounts
across all three features.

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
intersects them — any account in both lists is a confirmed bidirectional
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
Cross-reference the `ring_members` account IDs against the `is_fraud` ground
truth and you should see a high precision — the Louvain + bidirectional
intersection combo finds rings without needing labels.

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
       a.is_fraud            AS is_fraud,
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
Those are the strongest fraud candidates — three independent signals pointing
at the same account.

---

## Done in Aura

The graph now has three GDS-computed properties on every Account node:

- `risk_score` — centrality in the transfer network
- `community_id` — Louvain cluster assignment
- `similarity_score` — highest Jaccard similarity to any other account

**Next →** Return to Databricks and run `03_pull_and_model` to read these
features back and measure the ML lift.
