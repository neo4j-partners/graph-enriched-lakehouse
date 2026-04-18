# Graph-Enriched Lakehouse: Finance Genie

In this session, you will investigate a synthetic fraud dataset using two tools in sequence: Databricks Genie and Neo4j Graph Data Science.

Genie works against flat Delta tables. It can sort accounts by transfer volume, identify the most active bilateral pairs, and filter by merchant category. Those queries answer most questions a fraud analyst asks on a given morning. They do not answer questions about structural position in a transfer network, membership in a closed transfer ring, or shared merchant exposure across a group of accounts. The fraud in this dataset lives in exactly those three structures.

The session runs in two acts. In the first, you open a Genie space against the raw tables and work through five questions. Genie returns plausible answers. Each question is designed so that plausible and correct diverge: Genie's top results are not the fraud accounts, and the column values make clear why. In the second act, the same tables load into Neo4j Aura. PageRank, Louvain, and Node Similarity run against the graph and write three new columns back to the accounts table. Genie then answers the same questions correctly.

The session closes with a model comparison. A gradient-boosting classifier trained on baseline tabular features runs head-to-head against one trained with the three graph features, with the lift in fraud caught translated to an estimated dollar impact.

See [ADMIN_GUIDE.md](./ADMIN_GUIDE.md) for dataset design details, notebook descriptions, and pre-workshop setup instructions.

---

## Participant Notebook Flow

### 1. Prerequisites

- Access to the Databricks workspace
- The dedicated cluster with the Neo4j Spark Connector (provided by the admin)
- Neo4j Aura connection details: URI, username, and password (provided by the admin)

### 2. Run `00_required_setup.ipynb`

Import `00_required_setup.ipynb` into Databricks and attach it to the dedicated cluster. Three widgets appear at the top of the notebook:

```
Neo4j URI      neo4j+s://xxx.databases.neo4j.io
Neo4j Username neo4j
Neo4j Password <from Aura credentials file>
```

Enter the credentials provided by the admin, then run all cells. The notebook will:

1. Store the Neo4j credentials in the Databricks secret scope `neo4j-graph-engineering` under keys `uri`, `username`, and `password`
2. Verify the Aura connection

The Delta tables (`accounts`, `account_labels`, `merchants`, `transactions`, `account_links`) have been pre-loaded into the workspace by the workshop admin.

When the final cell prints `SETUP COMPLETE`, the environment is ready.

### 3. Explore the Raw Data in Genie

Open a Genie space against the Delta tables created in step 2 and work through the queries below. Note what each answer includes and what it leaves out. These are the questions GDS will resolve.

**"Which accounts are most central to the money flow?"**

Genie has no formal definition of centrality to work with. It interprets the question as a ranking problem and falls back on raw inbound transfer count, returning the whale accounts: normal accounts modeled as payment aggregators that collect many transfers from peripheral senders and send to many recipients. The ten fraud rings do not appear. Recursive centrality depends on *who* is sending, not how many transfers arrived, and no flat sort can capture that definition.

**"Which accounts receive the most transfers from other high-volume accounts?"**

The same question with the recursive hint spelled out in the phrasing. This tests whether Genie picks up on "from other high-volume accounts" and attempts a two-step ranking, or simply drops the qualifier and produces the same raw inbound sort as the previous question. In practice Genie has no graph traversal primitive, so the "high-volume" qualifier either gets flattened into a single-join filter or is dropped entirely, and the whale list returns unchanged. It is the same gap as the previous question, presented in the language that *would* trigger PageRank if the tooling could hear it.

**"Which groups of accounts are transferring money heavily among themselves?"**

Genie returns the top bilateral account pairs by transfer count, each with 3–4 mutual transfers. The pairs look isolated. There is no way to see from this view that they belong to ten rings of ~100 accounts each, each ring with an internal edge density far higher than the background rate.

**"Which accounts share the same spending patterns across merchants?"**

Genie counts shared merchants between account pairs. Nearly every pair shares at most one merchant. There is no column-level signal that separates fraud ring pairs, which share five specific anchor merchants, from the many random pairs that also share one merchant by coincidence.

**"Which accounts have the highest average transaction amount?"**

The tabular trap. In real fraud operations, compromised and money-mule accounts often carry elevated average transaction amounts. The operator pushes larger transactions through each account to maximize payout before detection. The synthetic data reflects that pattern deliberately: fraud accounts average $123.90 per transaction versus $111.77 for normal accounts, roughly 10.8% higher. Genie will sort on the mean and surface *some* fraud accounts in the tail.

The trap is that the distributions overlap almost entirely. Genie's top-N by average amount is dominated by high-spending normal accounts, not ring members. It is a real signal, but too diffuse to rank on. That is exactly what a production fraud team hits when amount-based rules catch a handful of brazen cases and miss the entire ring structure. GDS does not replace this signal; it complements it by ranking accounts on their position in the transfer network instead of the magnitude of their individual transactions.

The first five questions are the pivot point of the demo. Work through them, then try the additional test questions below.

---

**Additional test questions**

These are optional probes for how Genie handles weak tabular signals, null results, and multi-hop queries. The notes below each question are *predictions*. Test them in your Genie space and update the copy with what you actually see.

**"Which accounts transfer money at unusual hours?"**

Predicted result: Genie sorts by `txn_hour` outliers and returns accounts whose activity skews toward late-night or early-morning windows. The fraud-vs-normal hour gap is small (fraud mean 11.59, normal 12.33) and the distributions overlap heavily, so the top-N is dominated by noise rather than ring members. A representative dead-end: `txn_hour` is a meaningful feature in production fraud data but carries no separable signal in the synthetic dataset by design.

**"Which new accounts have the most transaction activity?"**

Predicted result: Genie filters `opened_date` to recent accounts and ranks by transaction count. Because `opened_date` is drawn uniformly across a five-year window in the synthetic data and is uncorrelated with ring membership, the top results do not cluster on fraud. A production fraud team would reach for this query early and find it unhelpful. The exercise shows that recency alone misses ring structure entirely.

**"Which accounts have the largest balance anomalies?"**

Predicted result: Balance is drawn uniformly from $100 to $500,000 with no fraud-vs-normal split (mean difference 0.05%). Genie returns the accounts with the highest and lowest balances and none of them cluster on fraud. A clean null result. Account-state columns do not expose the ring.

**"Which accounts send money to accounts that appear in other suspicious patterns?"**

Predicted result: A two-hop question. Genie cannot traverse relationships in a way that makes this query answerable, and at best returns accounts adjacent to the pairs surfaced in the community question above, a partial answer disconnected from the actual ring structure. The shape of this question is the shape of a graph, and only a graph engine can return the shape. This is the starkest tooling-gap question in the set.

### 4. Push to Neo4j

Run `01_neo4j_ingest` on the dedicated cluster. It clears the Neo4j graph, writes Account and Merchant nodes, and creates `TRANSACTED_WITH` (Account → Merchant) and `TRANSFERRED_TO` (Account → Account) relationships via the Spark Connector.

### 5. Compute Graph Features in Aura

Switch to the **Neo4j Aura Workspace → Query tab** and follow `02_aura_gds_guide`. The guide walks through:

1. Project the transfer graph as `account_transfers`
2. Run PageRank (20 iterations, damping factor 0.85) → writes `risk_score` to Account nodes
3. Run Louvain community detection → writes `community_id`
4. Run Node Similarity across the Account-Merchant bipartite graph → writes `similarity_score`

When the guide is complete, return to Genie and re-run the three queries from step 3. With `risk_score`, `community_id`, and `similarity_score` now available as columns, each question resolves.

### 6. Pull Features and Train Models

Run `03_pull_gold_tables` to read the enriched Account nodes back into Databricks, register the three graph features in Unity Catalog Feature Store, and train a head-to-head comparison:

- **Baseline:** balance, transaction aggregates, P2P counts, encoded categoricals
- **Graph-augmented:** baseline features plus `risk_score`, `community_id`, `similarity_score`

Both runs log to MLflow with AUC, precision, recall, F1, ROC curves, confusion matrices, and feature importance. The final cell translates the lift in fraud caught into an estimated dollar impact.

---

## Unity Catalog

Each participant's setup notebook creates a personal set of objects:

- **Catalog:** `graph_finance_demo_<username>`
- **Schema:** `neo4j_webinar`
- **Volume:** `source_data`

To change the catalog prefix, edit `CONFIG["catalog"]["prefix"]` in `setup/Includes/config.ipynb` before running the setup notebook.
