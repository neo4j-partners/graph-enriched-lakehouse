# Graph-Enriched Lakehouse Explorer

A Streamlit app deployed on Databricks Apps that interactively compares financial fraud data **before** and **after** Neo4j GDS graph enrichment.

## What This App Does

The app demonstrates that standard SQL analytics on flat lakehouse tables surface whale accounts (high-volume normals) instead of fraud ring members. After three Neo4j GDS algorithms write graph features back to the accounts table, the same questions resolve correctly.

### Pages

| Page | What It Shows |
|------|---------------|
| **Home** | Overview of the before/after narrative |
| **Before Enrichment** | Volume ranking, bilateral pairs, and transaction amount distributions. All are misleading. |
| **After Enrichment** | PageRank risk scores, Louvain communities, Node Similarity pairs, and enriched account table |

### Graph Algorithms Used

| Algorithm | Feature | Signal |
|-----------|---------|--------|
| **PageRank** | `risk_score` | Recursive centrality: ranks accounts by structural importance, not raw volume |
| **Louvain** | `community_id` | Community detection: reveals 10 fraud rings invisible to bilateral pair queries |
| **Node Similarity** | `similarity_score` | Jaccard similarity on merchant visits: exposes shared anchor merchant patterns |

## Data

All tables live in `graph-enriched-lakehouse.graph-enriched-schema`:

**Before enrichment:** `accounts`, `account_labels`, `transactions`, `account_links`, `merchants`

**After enrichment:** `gold_accounts`, `gold_account_similarity_pairs`, `account_graph_features`, `training_dataset`

## Prerequisites

- A Databricks workspace with access to the `graph-enriched-lakehouse` catalog
- A SQL Warehouse (Serverless or Pro, 2X-Small is sufficient)
- Databricks CLI installed and authenticated

## Local Development

The app uses a mock/real backend toggle. To run locally against your workspace:

```bash
# Set environment variables
export DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>
export CATALOG=graph-enriched-lakehouse
export SCHEMA=graph-enriched-schema

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
```

## Deploy to Databricks Apps

### 1. Configure the app

Edit `app.yaml` if needed. The default config uses a SQL Warehouse resource:

```yaml
command:
  - streamlit
  - run
  - app.py

resources:
  - name: sql-warehouse
    sql_warehouse:
      id: ${WAREHOUSE_ID}
      permission: CAN_USE

env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom: sql-warehouse
```

### 2. Create and deploy

```bash
# Create the app (first time only)
databricks apps create graph-lakehouse-explorer

# Deploy
databricks apps deploy graph-lakehouse-explorer --source-code-path ./app
```

### 3. Add resources

After creating the app, add the SQL Warehouse resource in the Databricks UI:
1. Navigate to **Apps → graph-lakehouse-explorer → Settings**
2. Click **+ Add resource**
3. Select **SQL Warehouse**, choose your warehouse, and set permission to **CAN_USE**

### 4. Verify

```bash
# Check app status
databricks apps get graph-lakehouse-explorer

# View logs if there are issues
databricks apps logs graph-lakehouse-explorer
```

## Project Structure

```
app/
├── app.py                          # Main entry point
├── backend.py                      # Data access layer (SQL queries)
├── pages/
│   ├── 1_Before_Enrichment.py      # Before enrichment explorer
│   └── 2_After_Enrichment.py       # After enrichment explorer
├── app.yaml                        # Databricks Apps config
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Roadmap

- [ ] **Phase 2:** Side-by-side comparison page + ML model results page
- [ ] **Phase 3:** Network visualization, live Neo4j queries, DABs deployment
