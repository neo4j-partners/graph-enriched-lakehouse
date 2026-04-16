# Finance-Genie Demo Flow — Major Gaps

Scope: end-to-end flow for the bare-minimum demo path:
data generation → 3 gap demos → GDS enrichment → gold tables → closes-gaps demo.
Model training and minor doc polish are intentionally out of scope.

---

## P0 — Will block the demo

### 1. Node Similarity `similarityCutoff=0.3` is far above the actual within-ring Jaccard (~0.011)

`feature_engineering/02_aura_gds_guide.ipynb` step 7 calls:

```python
gds.nodeSimilarity.write(G2, similarityMetric="JACCARD",
                         topK=5, similarityCutoff=0.3, ...)
```

`ADMIN_GUIDE.md` measures within-ring Jaccard at **0.011** (cross rate 0.0019).
With `cutoff=0.3` virtually no `SIMILAR_TO` relationships will be written,
which means:

- `Account.similarity_score` is set to 0.0 for almost every account in step 8.
- `gold_account_similarity_pairs` (written by `03_pull_gold_tables` §7) is empty
  or near-empty.
- `gds_enrichment_closes_gaps.ipynb` Check 3 (`same_ring_fraction > 60%`) cannot pass.

Fix: drop `similarityCutoff` (or set to 0.0) and rely on `topK=5` to control
output size. Alternatively, set cutoff to a value like 0.005 that is below the
within-ring mean but above the random-pair noise floor.

ADMIN_GUIDE.md is out of date ignore that.  What are the GDS best practices? Fix feature_engineering/02_aura_gds_guide.ipynb

### 2. `gds_enrichment_closes_gaps.ipynb` hard-codes `SPACE_ID`, but other demos use a secret

```python
SPACE_ID = "YOUR-GENIE-SPACE-ID"   # must be edited by hand
```

The three gap demos all read `dbutils.secrets.get("neo4j-graph-engineering",
"genie_space_id")`. The closes-gaps notebook will fail until the value is
manually replaced.

Compounding this, the secret scope only stores **one** `genie_space_id`. The
flow needs **two distinct Genie spaces** (one over raw tables for the gap demos,
one over `gold_accounts` + `gold_account_similarity_pairs` for the close-gaps
demo) — there is no convention for storing both.

Fix options: add a second secret key (e.g. `genie_space_id_after`) and have
closes-gaps read it; or document that the same notebook is reused after the
participant updates the secret.

For a quick fix gds_enrichment_closes_gaps.ipynb is just going to use the constant place holder and have the user create a second genie space and paste in the id.

### 3. `00_required_setup.ipynb` does not match what the README/ADMIN_GUIDE claim it does

README §2 and ADMIN_GUIDE both state the notebook:

- creates a per-user UC catalog (`graph_finance_demo_<username>`),
  schema (`neo4j_webinar`), and volume (`source_data`)
- generates the synthetic dataset and writes 5 Delta tables
- stores Neo4j credentials
- verifies the Aura connection

Reality: the notebook **only** stores Neo4j + Genie secrets and pings Aura.
Data generation lives in `setup/generate_data.py` (run via `uv` from a
terminal) and table creation lives in `setup/upload_and_create_tables.sh`
(run from a terminal).

A workshop participant following the README cannot reach a working state.
Either the notebook needs to do what the docs claim, or the docs need to be
rewritten around the shell flow.

ADMIN_GUIDE is out of date . Don't worry about that

### 4. Catalog/schema/volume names disagree across the repo

- README and ADMIN_GUIDE: `graph_finance_demo_<username>` / `neo4j_webinar` /
  `source_data`
- Every notebook and `upload_and_create_tables.sh`: `graph-enriched-lakehouse` /
  `graph-enriched-schema` / `graph-enriched-volume`

The notebooks won't see the tables a workshop participant would create if they
followed the docs. Pick one naming scheme and apply it everywhere.

notebooks are the source of truth just make sure they align. 

---

## P1 — Likely to derail a fresh setup

### 5. README/ADMIN references `03_pull_and_model`, file is `03_pull_gold_tables.ipynb`

README §6 says "Run `03_pull_and_model`". That filename does not exist.

### 6. No automated trigger for `setup/upload_and_create_tables.sh`

The shell script requires `DATABRICKS_WAREHOUSE_ID` exported in the user's
shell, plus a working `databricks` CLI profile. Nothing in any notebook runs
it or warns participants that it must be done before `00_required_setup`.

### 7. `account_labels` is leaked into Neo4j as a node property

`01_neo4j_ingest.ipynb` §3 joins `account_labels` into the accounts DataFrame
and pushes `is_fraud` to Neo4j as an Account node property. The "after-
enrichment" Genie space queries `gold_accounts`, which deliberately omits
`is_fraud` — but Neo4j still has it, and the Cypher in
`02_aura_gds_guide.ipynb` (e.g. step 3 PageRank verification) prints
`is_fraud` directly.

If the demo narrative is "Genie cannot see the label," shipping the label to
Neo4j and printing it in the GDS notebook undermines the story. The label is
needed only for the model-training notebook (out of scope here) — consider
keeping it in Databricks only and joining at training time.

### 8. README still describes a 5-question Genie flow; only 3 gap demos exist

README §3 walks through five questions. Only three have notebooks
(`hub_detection_no_threshold`, `community_structure_invisible`,
`merchant_overlap_volume_inflation`). Q5 (highest avg transaction amount) and
the four "additional test questions" are README-only. If "bare minimum" is the
goal, this is fine — but the README should be trimmed to match.

---

## P2 — Smaller alignment issues

### 9. `02_aura_gds_guide.ipynb` step 8 overwrites `similarity_score` with 0.0

Step 8 sets `a.similarity_score = COALESCE(MAX(s.similarity_score), 0.0)`. With
the cutoff bug above, every account that has no `SIMILAR_TO` edge ends up with
`0.0`. Even after fixing the cutoff, this design means accounts that
genuinely have no neighbors are indistinguishable from accounts that were
filtered out. Acceptable, but worth flagging.

### 10. `gold_account_similarity_pairs` dedup assumes both directions exist

`03_pull_gold_tables.ipynb` §7 filters `account_id_a < account_id_b` to
deduplicate. `gds.nodeSimilarity.write` writes one direction per pair, so the
filter may drop ~half the pairs depending on which direction was written. Use
`LEAST/GREATEST` ordering when materialising, or read with the connector
option that emits both directions.

### 11. README "5-year window" for `opened_date` is actually 1,800 days (~5 years) — fine

`generate_data.py` uses `timedelta(days=random.randint(0, 1800))`. Matches.
Listed for completeness.

### 12. `account_links.csv` uses `src_account_id` / `dst_account_id`; Neo4j ingest references them correctly

Verified — column names match across CSV → Delta → Spark connector
relationship write. No action needed.

---

## Data set alignment summary (what *is* aligned)

- All 5 CSV filenames (`accounts`, `account_labels`, `merchants`,
  `transactions`, `account_links`) match the table names the upload script
  creates and the notebooks query.
- `ground_truth.json` is uploaded to the same volume the demo notebooks read
  from.
- Column names and types in the upload script match what the notebooks expect
  (verified for `account_id`, `merchant_id`, `is_fraud`, `txn_hour`,
  `transfer_timestamp`).

---

## Open questions for you

1. **Genie space strategy.** Two spaces or one? If two, what naming
   convention do you want for the second secret (e.g. `genie_space_id_after`)?
2. **Catalog naming.** Keep `graph-enriched-lakehouse` everywhere and rewrite
   the README, or switch the notebooks to per-user catalogs?
3. **Setup automation scope.** Should `00_required_setup.ipynb` actually
   generate data and create the tables (so participants never touch the
   shell), or is the shell script the supported path and the docs are wrong?
4. **Node Similarity tuning.** Are you OK dropping `similarityCutoff` entirely
   and letting `topK=5` control fan-out, or do you want a measured cutoff
   (e.g. 0.005) tied to the verifier output?
5. **Label leakage to Neo4j.** Do you want me to strip `is_fraud` from the
   01_neo4j_ingest write and from the verification Cypher in 02, or leave it
   in for presenter convenience?
