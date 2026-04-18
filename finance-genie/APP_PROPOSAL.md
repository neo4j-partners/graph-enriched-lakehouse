# App Proposal: Graph-Enriched Lakehouse Explorer

> **Goal:** A Databricks App that lets fraud analysts and demo audiences interactively compare lakehouse data **before** and **after** Neo4j GDS enrichment — surfacing the blind spots that flat tables hide and the signals that graph algorithms reveal.

---

## Progress Tracker

| Phase | Status | Notes |
|-------|--------|-------|
| **Phase 1: Core App** | ✅ Complete | Scaffold, backend, Before + After pages deployed |
| **Phase 2: Comparison & Model** | ⬜ Not started | Side-by-side page, ML model results, business impact calc |
| **Phase 3: Enhancements** | ⬜ Not started | Network viz, live Neo4j, DABs, Dash migration |

### Phase 1 Deliverables

| File | Status | Description |
|------|--------|-------------|
| `app/app.yaml` | ✅ | Streamlit command, SQL Warehouse resource via `valueFrom` |
| `app/requirements.txt` | ✅ | `databricks-sql-connector`, `databricks-sdk`, `plotly>=5.18` |
| `app/backend.py` | ✅ | 12 cached query functions against all 8 tables |
| `app/app.py` | ✅ | Multi-page entry point with overview narrative |
| `app/pages/1_Before_Enrichment.py` | ✅ | Volume ranking, bilateral pairs, txn amount dist, KPIs |
| `app/pages/2_After_Enrichment.py` | ✅ | Risk scores, community explorer, similarity pairs, enriched table |
| `app/README.md` | ✅ | Setup, deployment, and usage instructions |

---

## 1. Context

The `finance-genie` project generates a synthetic fraud dataset of 25,000 accounts, 300k P2P transfers, and 10 embedded fraud rings. Five notebooks form the pipeline:

| Step | Notebook | What It Does |
|------|----------|--------------|
| 0 | `00_required_setup` | Stores Neo4j Aura credentials |
| 1 | `01_neo4j_ingest` | Pushes accounts, merchants, and transfers to Neo4j |
| 2 | `02_aura_gds_guide` | Runs PageRank, Louvain, and Node Similarity in Aura |
| 3 | `03_pull_gold_tables` | Pulls graph features back to Delta; builds gold + training tables |
| 4 | `04_train_model` | Trains baseline vs graph-augmented GBM; logs to MLflow |

The core narrative: Genie (and any flat-table tool) answers fraud questions plausibly but *incorrectly* — sorting by volume surfaces whales, not ring members. After three GDS algorithms write `risk_score`, `community_id`, and `similarity_score` back to accounts, the same questions resolve correctly.

The app makes this narrative **interactive and self-service** — no notebooks required.

---

## 2. Data Sources

All tables live in **`graph-enriched-lakehouse`.`graph-enriched-schema`**.

### Before Enrichment (raw lakehouse)

| Table | Key Columns | Role |
|-------|-------------|------|
| `accounts` | `account_id`, `account_type`, `region`, `balance`, `holder_age`, `opened_date` | Core account dimension |
| `transactions` | `account_id`, `merchant_id`, `amount`, `txn_hour` | Transactional fact table |
| `account_links` | `src_account_id`, `dst_account_id`, `amount` | P2P transfer edges |
| `merchants` | `merchant_id`, `category` | Merchant dimension |
| `account_labels` | `account_id`, `is_fraud` | Ground truth (hidden from Genie, available for model eval) |

### After Enrichment (graph-augmented)

| Table | Key Columns | Algorithm Source |
|-------|-------------|------------------|
| `account_graph_features` | `account_id`, `risk_score`, `community_id`, `similarity_score` | Feature Store table with PK |
| `gold_accounts` | All account cols + `risk_score`, `community_id`, `similarity_score` | Joined gold table for Genie |
| `gold_account_similarity_pairs` | `account_id_a`, `account_id_b`, `similarity_score` | Node Similarity relationship pairs |
| `training_dataset` | Tabular features + graph features + `is_fraud` | Full ML-ready dataset |

---

## 3. App Architecture

### Framework: **Streamlit**

Streamlit is the right choice here because:
- Rapid prototyping — matches the demo/workshop context
- Built-in data visualization (tables, charts, metrics) with minimal code
- Pre-installed on Databricks Apps runtime (no extra dependencies for core framework)
- Native support for interactive widgets (sliders, dropdowns, tabs) that map directly to the before/after comparison UX

For a future production version with richer interactivity (cross-filtering, drill-down), Dash with `dash-bootstrap-components` would be the upgrade path.

### Backend: SQL Warehouse

The app queries Delta tables through a Databricks SQL Warehouse via `databricks-sql-connector`. All data is pre-materialized in gold tables — no heavy computation at query time.

### Auth: Service Principal (App Auth)

The app uses `databricks.sdk.core.Config()` for automatic credential injection. The SQL Warehouse is declared as an app resource in `app.yaml` via `valueFrom`.

### File Structure

```
finance-genie/app/
├── app.py                          # Main Streamlit application
├── backend.py                      # SQL queries and data access layer
├── pages/
│   ├── 1_Before_Enrichment.py      # Before-enrichment explorer
│   └── 2_After_Enrichment.py       # After-enrichment explorer
├── requirements.txt                # databricks-sql-connector, plotly
├── app.yaml                        # Databricks Apps config
└── README.md
```

---

## 4. App Pages

### Page 1: Before Enrichment — "What Flat Tables Show"

Reproduces the Genie demo questions against raw tables and shows why each answer is misleading.

**Components:**

- **Top Accounts by Transfer Volume** — ranked bar chart of accounts by inbound P2P count. Highlights that the top-N are whale accounts (normal), not fraud ring members. Color-codes by `is_fraud` to reveal the gap.
- **Bilateral Transfer Pairs** — table of top account pairs by mutual transfer count (3–4 transfers each). Shows isolated pairs with no visible ring structure.
- **Transaction Amount Distribution** — overlapping histograms of avg transaction amount for fraud vs normal accounts. Shows the 10.8% gap ($123.90 vs $111.77) that is real but too diffuse to rank on.
- **Summary Metrics** — KPI cards showing: total accounts, total fraud accounts, % fraud caught by top-200 volume sort, % fraud caught by top-200 avg amount sort.

### Page 2: After Enrichment — "What Graph Algorithms Reveal"

The same data, now augmented with GDS features, answering the same questions correctly.

**Components:**

- **PageRank Risk Scores** — histogram + box plot of `risk_score` distribution by fraud status, plus scatter plot of risk_score vs balance. Shows clear separation: fraud accounts average 3.65× higher risk score than normal.
- **Louvain Communities** — bar chart of top 20 communities by fraud count with purity coloring. Interactive community explorer: dropdown selects a `community_id` and shows member accounts with metrics.
- **Node Similarity Pairs** — histogram of top-200 similarity pairs colored by pair type (Both Fraud / Mixed / Both Normal). Expandable full table view.
- **Enriched Account Table** — full `gold_accounts` table sorted by risk_score with checkbox filter for fraud-only view.
- **Summary Metrics** — KPI cards showing: % fraud caught by top-200 risk_score sort, risk score separation ratio, fraud avg risk score.

### Page 3: Side-by-Side Comparison *(Phase 2)*

The "aha moment" — same question, two answers.

**Components:**

- **Dual-column layout** for each of the five core Genie questions:
  1. "Most central accounts" → Volume sort vs PageRank sort
  2. "Tightly connected groups" → Bilateral pairs vs Louvain communities
  3. "Shared spending patterns" → 1-merchant overlap vs Node Similarity scores
  4. "Highest avg transaction" → Amount sort vs Graph-augmented ranking
  5. "Accounts receiving from high-volume senders" → Raw inbound vs Recursive centrality
- **Precision/Recall gauges** for each approach (fraud accounts in top-N)
- **Toggle** — switch between showing/hiding fraud labels to let the audience guess first

### Page 4: Model Results — "The Money Slide" *(Phase 2)*

Visualizes the ML model comparison from `04_train_model`.

**Components:**

- **Metric Comparison Table** — AUC, Precision, Recall, F1 for Baseline vs Graph-Augmented
- **ROC Curve Overlay** — dual ROC curves with AUC annotations
- **Confusion Matrix Side-by-Side** — baseline vs graph-augmented
- **Feature Importance** — horizontal bar chart of top-15 features from the graph-augmented model, with graph features highlighted in a distinct color
- **Business Impact Calculator** — interactive slider for "avg fraud loss per case" (default $5,000); computes estimated annual savings from the additional fraud cases caught

---

## 5. Key Interactions

| Interaction | Widget | Effect |
|-------------|--------|--------|
| Select community | Dropdown | Filters community explorer to one Louvain cluster |
| Adjust top-N | Slider (50–500) | Recalculates precision/recall for volume vs graph ranking |
| Toggle fraud labels | Checkbox | Hides/reveals ground truth coloring |
| Fraud loss estimate | Slider ($1k–$50k) | Updates business impact calculation *(Phase 2)* |
| Account deep-dive | Click account row | Expands to show all features *(Phase 2)* |

---

## 6. Implementation Plan

### Phase 1: Core App ✅

| Task | Status | Details |
|------|--------|---------|
| Scaffold project | ✅ | Created `app/` directory, `app.yaml`, `requirements.txt` |
| Backend layer | ✅ | 12 query functions against all 8 tables via `databricks-sql-connector` |
| Page 1: Before | ✅ | Volume ranking, bilateral pairs, amount distribution, KPIs |
| Page 2: After | ✅ | Risk score histograms, community explorer, similarity pairs, enriched table |
| README.md | ✅ | Setup, deployment, and usage documentation |
| Deploy v0.1 | ⬜ | `databricks apps deploy` with SQL Warehouse resource |

### Phase 2: Comparison & Model

| Task | Details |
|------|---------|
| Page 3: Side-by-side | Dual-column layout, precision/recall gauges, fraud label toggle |
| Page 4: Model results | Read MLflow metrics (or query `training_dataset` for live computation) |
| Business impact calc | Interactive slider with dollar estimates |
| Polish | Consistent styling, loading states, error handling |
| Deploy v1.0 | Full feature release |

### Phase 3: Enhancements (Optional)

| Task | Details |
|------|---------|
| Network visualization | Use `pyvis` or `streamlit-agraph` to render subgraph around selected account |
| Live Neo4j queries | Optional toggle to query Neo4j directly for real-time graph traversal |
| DABs deployment | Migrate from CLI deploy to Databricks Asset Bundles for CI/CD |
| Migrate to Dash | If richer interactivity (cross-filtering, callbacks) is needed |

---

## 7. App Resources (`app.yaml`)

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
  - name: CATALOG
    value: graph-enriched-lakehouse
  - name: SCHEMA
    value: graph-enriched-schema
```

---

## 8. Dependencies (`requirements.txt`)

```
databricks-sql-connector
databricks-sdk
plotly>=5.18
```

Note: `streamlit` is pre-installed on the Databricks Apps runtime (v1.38.0). No need to pin it unless a newer version is required.

---

## 9. Success Criteria

| Criterion | Measure |
|-----------|---------|
| Before/after narrative is clear | Non-technical audience can articulate why flat tables miss fraud rings after using the app |
| Interactive exploration works | Analysts can filter by community, sort by risk score, and drill into individual accounts |
| Model lift is quantified | Business impact calculator shows dollar savings from graph enrichment |
| Deployment is reproducible | `databricks apps deploy` from the `app/` directory succeeds on first try |
| Performance | All pages load in <3 seconds against pre-materialized gold tables |

---

## 10. Open Questions

1. **Auth model** — Should the app use service principal auth (simpler) or on-behalf-of user auth (respects per-user table ACLs)? For a demo app, SP auth is sufficient.
2. **MLflow integration** — Should Page 4 read metrics directly from MLflow experiment runs, or query the `training_dataset` and compute metrics live? MLflow is cleaner but requires the experiment to exist.
3. **Network visualization** — Is a graph rendering of fraud rings (via `pyvis`/`streamlit-agraph`) worth the Phase 3 investment, or do the tabular/chart views suffice?
4. **SQL Warehouse sizing** — The gold tables are small (~25k rows). A serverless SQL Warehouse (2X-Small) should be more than sufficient.
