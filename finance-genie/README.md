# Graph-Enriched Lakehouse — Finance Genie

Genie can answer most questions a fraud analyst asks against raw Delta tables. It can sort accounts by inbound transfer volume, find account pairs with the most mutual transfers, and filter by merchant risk tier. What it cannot do is identify which account sits at the structural center of a money-flow network, which accounts form a closed transfer ring regardless of individual volume, or which accounts share the same small set of merchants in a pattern too sparse for any column filter to catch. Those three gaps are what this demo is designed to expose.

The walkthrough runs in two acts. In the first act, participants open a Genie space against the raw Delta tables and work through three fraud-investigation queries. Genie returns plausible but structurally incomplete answers. In the second act, the same tables are loaded into Neo4j Aura, PageRank, Louvain, and Node Similarity run as GDS algorithms, and the results write back to the lakehouse as three new columns on the accounts table. Genie then answers the same questions with full structural depth.

---

## The Dataset and Why It's Designed This Way

The synthetic dataset contains 25,000 accounts, 2,500 merchants, 250,000 transactions, and 40,000 peer-to-peer transfers. One thousand accounts (4%) are planted as fraud, distributed across ten rings of approximately 100 accounts each.

Every fraud pattern is calibrated to expose exactly one gap between Genie's column-based analysis and GDS graph analysis. Tabular signals — transaction amounts, hours, merchant tier fractions — are kept nearly identical between fraud and normal accounts. The signal lives in structure.

### Whale Accounts Hide the Ring from Raw Sorting (PageRank)

Two hundred normal accounts are designated as P2P "whales." They receive 20% of all transfer links, giving them raw inbound counts of 50–60 each. Fraud ring members receive approximately 12 links each from within-ring transfers.

When Genie sorts accounts by inbound transfer count, the top 20 results are all whales. None are fraud ring members. Whales attract transfers from low-degree peripheral accounts, so their recursive hub score (PageRank) is moderate despite the high raw count. Ring members receive from other ring members who also have elevated connectivity — their PageRank compounds through the ring topology.

The demo gap: Genie names whales. PageRank names the ring.

### Ten Rings Produce a 268x Density Signal (Louvain)

The ten fraud rings are partitioned before any links are generated. Within-ring P2P links account for 30% of all 40,000 transfers, distributed randomly across ring pairs rather than concentrated on specific bilateral relationships. This keeps individual pair counts at 1–4 transfers — low enough that Genie's top bilateral pairs look like isolated suspicious activity rather than a ring.

Within-ring edge density is 0.024. Between-account background density is 0.00009. The ratio is approximately 268x. Louvain resolves this into ten communities of ~100 accounts each. Genie sees 15 suspicious pairs involving ~30 accounts. Louvain finds all 1,000.

The demo gap: Genie finds hints of fraud at the pair level. Louvain finds the ring.

### Anchor Merchants Create Jaccard Signal Without a Column Signal (Node Similarity)

Each ring is assigned five specific anchor merchants, sampled from the full merchant pool rather than exclusively from high-risk merchants. Fraud accounts transact at a ring anchor 18% of the time. Because the anchors are drawn from all 2,500 merchants, the overall high-risk merchant fraction for fraud accounts (23.4%) stays within 2.4 percentage points of normal accounts (21.0%) — not enough for a merchant-tier column filter to be useful.

The structural signal is that ring members share the same five specific merchants. Average Jaccard similarity within a ring is 1.78x higher than the fraud-to-normal cross rate. GDS Node Similarity scores every account pair by merchant-set overlap simultaneously; Genie can only count raw shared merchants, where nearly all pairs share at most one.

The demo gap: Genie finds account pairs with one shared merchant. Node Similarity scores the full bipartite overlap and surfaces the ring.

---

## Notebooks

| # | File | Runs In | Purpose |
|---|------|---------|---------|
| 0 | `0 - Required Setup.ipynb` | Databricks | Widget-based setup: creates a per-user Unity Catalog, generates the synthetic dataset as Delta tables, stores Neo4j credentials as Databricks secrets, and verifies the Aura connection. |
| 01 | `01_neo4j_ingest.py` | Databricks | Pushes the operational Delta tables (`accounts`, `merchants`, `transactions`, `account_links`) into Neo4j Aura as a typed property graph via the Neo4j Spark Connector. |
| 02 | `02_aura_gds_guide.py` | Neo4j Aura Workspace | Cypher and GDS commands to project the graph, run PageRank / Louvain / Node Similarity, and write `risk_score`, `community_id`, and `similarity_score` back as Account node properties. Also available as [`aura_gds_guide.md`](./aura_gds_guide.md). |
| 03 | `03_pull_and_model.py` | Databricks | Reads enriched Account nodes back via the Spark Connector, registers graph features in Unity Catalog Feature Store, trains a baseline vs graph-augmented `GradientBoostingClassifier`, and compares AUC / F1 / ROC curves with an estimated dollar impact from additional fraud caught. |

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

This writes four CSV files to `./data/` with no Databricks dependency — only `pandas` and Python 3.9+ required. Inspect the outputs to confirm:

- `accounts.csv` — 25,000 rows, 1,000 marked `is_fraud = True`
- `merchants.csv` — 2,500 rows across eight categories and three risk tiers
- `transactions.csv` — 250,000 rows, fraud transactions at ~10,100 (~4%)
- `account_links.csv` — 40,000 rows, 30% concentrated within the ten fraud rings

The CSVs are for local inspection only. The setup notebook generates the Delta tables independently when each participant runs it.

### 3. Prepare the Workspace

Before participants arrive:

- Confirm the dedicated cluster has the Neo4j Spark Connector Maven library attached and is running on Runtime 13.3 LTS or higher
- Confirm participants have `CREATE CATALOG` permission in the Unity Catalog metastore, or pre-create a catalog they can write to
- Share the Neo4j Aura connection details (URI, username, password) with participants — each participant enters these into the setup notebook widgets

---

## Participant Notebook Flow

### 1. Prerequisites

- Access to the Databricks workspace
- The dedicated cluster with the Neo4j Spark Connector (provided by the admin)
- Neo4j Aura connection details (URI, username, password — provided by the admin)

### 2. Run `0 - Required Setup.ipynb`

Import `0 - Required Setup.ipynb` into Databricks and attach it to the dedicated cluster. Three widgets appear at the top of the notebook:

```
Neo4j URI      neo4j+s://xxx.databases.neo4j.io
Neo4j Username neo4j
Neo4j Password <from Aura credentials file>
```

Enter the credentials provided by the admin, then run all cells. The notebook will:

1. Create a personal Unity Catalog (`graph_finance_demo_<your_username>`), schema (`neo4j_webinar`), and volume
2. Generate the synthetic fraud dataset and write it to five Delta tables: `accounts`, `account_labels`, `merchants`, `transactions`, `account_links`. Fraud labels are withheld from the operational tables — `account_labels` maps each account to its ground truth and is used only in notebook 03 for model training and evaluation.
3. Store the Neo4j credentials in the Databricks secret scope `neo4j-graph-engineering` under keys `uri`, `username`, and `password`
4. Verify the Aura connection

When the final cell prints `SETUP COMPLETE`, the environment is ready.

### 3. Explore the Raw Data in Genie

Open a Genie space against the Delta tables created in step 2 and try these three queries. Note what each answer includes and what it leaves out — these are the questions GDS will resolve.

**"Which accounts receive the most transfers from other high-volume accounts?"**

Genie sorts by raw inbound count and returns the whale accounts — normal accounts with high transfer volume. The ten fraud rings do not appear. The structurally central accounts are invisible to a volume sort because centrality depends on who is sending, not how many transfers arrived.

**"Which groups of accounts are transferring money heavily among themselves?"**

Genie returns the top bilateral account pairs by transfer count, each with 3–4 mutual transfers. The pairs look isolated. There is no way to see from this view that they belong to ten rings of ~100 accounts each, each ring with an internal edge density 268x higher than the background rate.

**"Which accounts share the same spending patterns across merchants?"**

Genie counts shared merchants between account pairs. Nearly every pair shares at most one merchant. There is no column-level signal that separates fraud ring pairs — who share five specific anchor merchants — from the many random pairs that also share one merchant by coincidence.

**"Which accounts have the highest average transaction amount?"**

The tabular trap. In real fraud operations, compromised and money-mule accounts often carry elevated average transaction amounts — the operator pushes larger transactions through each account to maximize payout before detection. The synthetic data reflects that pattern deliberately: fraud accounts average $123.90 per transaction versus $111.77 for normal accounts, roughly 10.8% higher. Genie will sort on the mean and surface *some* fraud accounts in the tail.

The trap is that the distributions overlap almost entirely. Genie's top-N by average amount is dominated by high-spending normal accounts, not ring members. It is a real signal, but too diffuse to rank on — exactly what a production fraud team hits when amount-based rules catch a handful of brazen cases and miss the entire ring structure. GDS does not replace this signal; it complements it by ranking accounts on their position in the transfer network instead of the magnitude of their individual transactions.

Together, these answers are the pivot point of the demo. Try any other fraud-investigation questions that come to mind before moving on.

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

Run `03_pull_and_model` to read the enriched Account nodes back into Databricks, register the three graph features in Unity Catalog Feature Store, and train a head-to-head comparison:

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
