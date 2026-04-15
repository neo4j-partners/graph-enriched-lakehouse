# Databricks notebook source
# MAGIC %md
# MAGIC # Graph-Augmented Intelligence — Webinar
# MAGIC ## Notebook 02: GDS Algorithms in Neo4j Aura
# MAGIC
# MAGIC **This notebook is a reference guide.** Run these commands in the
# MAGIC **Neo4j Aura Workspace** (Query tab) — not in Databricks.
# MAGIC
# MAGIC After running `01_neo4j_ingest`, switch to Aura and execute the steps below.
# MAGIC When finished, return to Databricks and run `03_pull_and_model`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### What We're Computing
# MAGIC
# MAGIC | Algorithm | Property Written | Fraud Signal |
# MAGIC |-----------|-----------------|-------------|
# MAGIC | **PageRank** | `Account.risk_score` | Central accounts in money-flow networks |
# MAGIC | **Louvain** | `Account.community_id` | Tightly connected clusters (fraud rings) |
# MAGIC | **Node Similarity** | `Account.similarity_score` | Accounts sharing the same merchants |

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 1: Verify the Graph Loaded Correctly
# MAGIC
# MAGIC Run in Aura Workspace → Query tab:
# MAGIC
# MAGIC ```cypher
# MAGIC // Check node and relationship counts
# MAGIC MATCH (a:Account) WITH count(a) AS accounts
# MAGIC MATCH (m:Merchant) WITH accounts, count(m) AS merchants
# MAGIC MATCH ()-[t:TRANSACTED_WITH]->() WITH accounts, merchants, count(t) AS txns
# MAGIC MATCH ()-[p:TRANSFERRED_TO]->() WITH accounts, merchants, txns, count(p) AS p2p
# MAGIC RETURN accounts, merchants, txns, p2p
# MAGIC ```
# MAGIC
# MAGIC **Expected:** ~5,000 accounts, ~500 merchants, ~50,000 transactions, ~8,000 transfers.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 2: Project the Account Transfer Graph
# MAGIC
# MAGIC GDS algorithms run on an **in-memory graph projection**, not directly on the database.
# MAGIC This projects only Account nodes and TRANSFERRED_TO relationships — the peer-to-peer
# MAGIC money-flow graph where fraud rings live.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.graph.project(
# MAGIC   'account_transfers',
# MAGIC   'Account',
# MAGIC   {TRANSFERRED_TO: {orientation: 'UNDIRECTED'}}
# MAGIC )
# MAGIC YIELD graphName, nodeCount, relationshipCount
# MAGIC RETURN graphName, nodeCount, relationshipCount
# MAGIC ```
# MAGIC
# MAGIC **Expected:** ~5,000 nodes, ~8,000 relationships.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 3: Run PageRank (Risk Centrality)
# MAGIC
# MAGIC PageRank measures how "central" an account is in the transfer network.
# MAGIC Accounts that receive money from many well-connected accounts score higher —
# MAGIC exactly how money-mule networks operate.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.pageRank.write(
# MAGIC   'account_transfers',
# MAGIC   {
# MAGIC     maxIterations: 20,
# MAGIC     dampingFactor: 0.85,
# MAGIC     writeProperty: 'risk_score'
# MAGIC   }
# MAGIC )
# MAGIC YIELD nodePropertiesWritten, ranIterations, didConverge
# MAGIC RETURN nodePropertiesWritten, ranIterations, didConverge
# MAGIC ```
# MAGIC
# MAGIC **Verify — top 10 by PageRank:**
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC WHERE a.risk_score IS NOT NULL
# MAGIC RETURN a.account_id AS id,
# MAGIC        a.is_fraud AS fraud,
# MAGIC        round(a.risk_score, 6) AS pagerank
# MAGIC ORDER BY a.risk_score DESC
# MAGIC LIMIT 10
# MAGIC ```
# MAGIC
# MAGIC Look for fraud accounts appearing in the top results — that's the signal.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 4: Run Louvain Community Detection (Fraud Rings)
# MAGIC
# MAGIC Louvain finds clusters of densely connected accounts. In a legitimate network,
# MAGIC communities are large and diffuse. Fraud rings form **small, tight clusters**
# MAGIC with heavy internal transfers.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.louvain.write(
# MAGIC   'account_transfers',
# MAGIC   {
# MAGIC     writeProperty: 'community_id'
# MAGIC   }
# MAGIC )
# MAGIC YIELD communityCount, modularity, nodePropertiesWritten
# MAGIC RETURN communityCount, modularity, nodePropertiesWritten
# MAGIC ```
# MAGIC
# MAGIC **Verify — community size distribution:**
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC WHERE a.community_id IS NOT NULL
# MAGIC RETURN a.community_id AS community, count(*) AS size
# MAGIC ORDER BY size DESC
# MAGIC LIMIT 15
# MAGIC ```
# MAGIC
# MAGIC **Visualise a fraud-heavy community:**
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC WHERE a.community_id IS NOT NULL AND a.is_fraud = true
# MAGIC WITH a.community_id AS community, count(*) AS fraud_count
# MAGIC ORDER BY fraud_count DESC LIMIT 1
# MAGIC WITH community
# MAGIC MATCH (m:Account {community_id: community})-[r:TRANSFERRED_TO]-(other:Account {community_id: community})
# MAGIC RETURN m, r, other
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 5: Drop the Transfer Graph Projection
# MAGIC
# MAGIC Clean up before creating the next projection.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.graph.drop('account_transfers')
# MAGIC YIELD graphName
# MAGIC RETURN graphName
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 6: Project the Bipartite Graph (Account → Merchant)
# MAGIC
# MAGIC Node Similarity needs the bipartite graph: which accounts transact
# MAGIC with which merchants.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.graph.project(
# MAGIC   'account_merchants',
# MAGIC   ['Account', 'Merchant'],
# MAGIC   {TRANSACTED_WITH: {orientation: 'NATURAL'}}
# MAGIC )
# MAGIC YIELD graphName, nodeCount, relationshipCount
# MAGIC RETURN graphName, nodeCount, relationshipCount
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 7: Run Node Similarity (Shared Merchant Patterns)
# MAGIC
# MAGIC Two accounts are similar if they transact with the **same merchants**.
# MAGIC Fraud accounts typically share a small set of high-risk merchants.
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.nodeSimilarity.write(
# MAGIC   'account_merchants',
# MAGIC   {
# MAGIC     similarityMetric: 'JACCARD',
# MAGIC     topK: 5,
# MAGIC     similarityCutoff: 0.3,
# MAGIC     writeRelationshipType: 'SIMILAR_TO',
# MAGIC     writeProperty: 'similarity_score'
# MAGIC   }
# MAGIC )
# MAGIC YIELD nodesCompared, relationshipsWritten
# MAGIC RETURN nodesCompared, relationshipsWritten
# MAGIC ```
# MAGIC
# MAGIC **Verify — most similar account pairs:**
# MAGIC ```cypher
# MAGIC MATCH (a:Account)-[s:SIMILAR_TO]-(b:Account)
# MAGIC WHERE a.account_id < b.account_id
# MAGIC RETURN a.account_id AS account_a,
# MAGIC        b.account_id AS account_b,
# MAGIC        round(s.similarity_score, 3) AS similarity,
# MAGIC        a.is_fraud AS a_fraud,
# MAGIC        b.is_fraud AS b_fraud
# MAGIC ORDER BY s.similarity_score DESC
# MAGIC LIMIT 10
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 8: Aggregate Max Similarity per Account
# MAGIC
# MAGIC For each account, store its **highest similarity score** as a node property.
# MAGIC This makes it easy to read back as a single feature column in Databricks.
# MAGIC
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC OPTIONAL MATCH (a)-[s:SIMILAR_TO]-()
# MAGIC WITH a, COALESCE(MAX(s.similarity_score), 0.0) AS max_sim
# MAGIC SET a.similarity_score = max_sim
# MAGIC RETURN count(a) AS accounts_updated
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 9: Drop the Bipartite Graph Projection
# MAGIC
# MAGIC ```cypher
# MAGIC CALL gds.graph.drop('account_merchants')
# MAGIC YIELD graphName
# MAGIC RETURN graphName
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Step 10: Final Verification — All Features Written
# MAGIC
# MAGIC Confirm all three properties exist on Account nodes:
# MAGIC
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC WHERE a.risk_score IS NOT NULL
# MAGIC   AND a.community_id IS NOT NULL
# MAGIC   AND a.similarity_score IS NOT NULL
# MAGIC RETURN count(a) AS accounts_with_all_features
# MAGIC ```
# MAGIC
# MAGIC **Fraud vs legitimate comparison:**
# MAGIC ```cypher
# MAGIC MATCH (a:Account)
# MAGIC RETURN a.is_fraud AS is_fraud,
# MAGIC        count(a) AS count,
# MAGIC        round(avg(a.risk_score), 6) AS avg_pagerank,
# MAGIC        round(avg(a.similarity_score), 4) AS avg_similarity,
# MAGIC        count(DISTINCT a.community_id) AS num_communities
# MAGIC ORDER BY a.is_fraud
# MAGIC ```
# MAGIC
# MAGIC You should see clear separation between fraud and legitimate accounts
# MAGIC across all three features.

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC ## Done in Aura!
# MAGIC
# MAGIC The graph now has three GDS-computed properties on every Account node:
# MAGIC - `risk_score` — centrality in the transfer network
# MAGIC - `community_id` — Louvain cluster assignment
# MAGIC - `similarity_score` — highest Jaccard similarity to any other account
# MAGIC
# MAGIC **Next →** Return to Databricks and run `03_pull_and_model` to read these
# MAGIC features back and measure the ML lift.
