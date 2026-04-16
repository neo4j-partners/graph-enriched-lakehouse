# Node Similarity Validation Plan

## Current state (2026-04-16)

New CSVs have been regenerated locally with the final parameter set below. **They have not yet been uploaded to Databricks.** The current Neo4j graph still contains the old data (NUM_MERCHANTS=2500, RING_ANCHOR_PREF=0.09, WITHIN_RING_PROB=0.12). All GDS steps below are pending until upload and notebook 00/01 re-run complete.

**Final parameter set (all four `verify_fraud_patterns.py` checks pass):**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `NUM_MERCHANTS` | 7,500 | Up from 2,500 — reduces noise floor |
| `RING_ANCHOR_PREF` | 0.40 | Up from 0.09 — boosts ring signal |
| `RING_ANCHOR_CNT` | 4 | Unchanged from Phase 2 .env |
| `WITHIN_RING_PROB` | 0.50 | Restored to config default (was 0.12) |
| `WHALE_INBOUND` | 0.20 | Unchanged from Phase 2 .env |
| `WHALE_OUTBOUND` | 0.20 | Set to match WHALE_INBOUND (symmetric) |
| `CAPTAIN_TRANSFER_PROB` | 0.02 | Reduced from 0.10 (see research notes) |
| `WHALE_FIXED_OUTBOUND` | true | Unchanged |

**`verify_fraud_patterns.py` results with new CSVs:**

| Check | Key metric | Value | Pass? |
|-------|-----------|-------|-------|
| Whale-Hiding-PageRank | top_200_whales / top_200_fraud | 183 / 17 | ✅ |
| Ring Density Ratio | within-ring / background | 6,428x | ✅ |
| Anchor Jaccard | within-ring / cross-ring ratio | 191.7x | ✅ |
| Column Signal Sanity | high-risk fraction gap | 0.55 pp | ✅ |

## What we are measuring

Node Similarity has two separate pass criteria:

**Criterion A** — `run_and_verify_gds.py` `check_similarity()`:
Fraud avg `similarity_score` / normal avg `similarity_score` >= 2.0. The `similarity_score` property stored on each Account node is the MAX Jaccard across its top-10 `SIMILAR_TO` neighbors. This measures whether the GDS feature separates fraud from normal across the full population.

**Criterion B** — Demo notebook Check 3 (`genie_demos/gds_enrichment_closes_gaps.ipynb`):
Same-ring fraction of pairs Genie returns from `gold_account_similarity_pairs` > 60%. Genie asks "which pairs of accounts share the most similar merchant visit patterns?" and queries the gold table. This measures whether the top-scoring SIMILAR_TO pairs are same-ring pairs, from the user's perspective.

Both must pass for the demo to work end to end.

## Step 1 — Validate graph structure

Run from `finance-genie/validation/`:

```bash
uv run validate_neo4j_graph.py
```

Record the structural baseline in the table below before any GDS work. This confirms the new CSV data made it through the Databricks → Neo4j ingest correctly. If this fails, stop here and diagnose the ingest.

**Target values:**
- Account count: 25,000
- Merchant count: 7,500
- Within-ring density ratio: > 100x (expect ~6,000x based on verify_fraud_patterns.py with new parameters)
- Per-ring anchor visit ratio: > 10x for all 10 rings

## Step 2 — Run GDS pipeline and record all baselines

Run from `finance-genie/validation/`:

```bash
uv run run_and_verify_gds.py
```

This writes GDS properties to Neo4j (risk_score, community_id, similarity_score, SIMILAR_TO edges) and then runs all four verification checks. Record every number in the table below.

**Pass targets for this run:**
- PageRank top-20 fraud fraction >= 50%
- PageRank fraud/normal avg ratio >= 2.0
- Louvain avg purity across rings >= 50%
- Louvain per-ring coverage >= 80% for all rings
- Node Similarity relationship count ~250,000
- Node Similarity fraud/normal avg ratio >= 2.0 (Criterion A)

## Step 3 — Rebuild gold tables

After Step 2 writes properties to Neo4j, run notebook 03 sections 6 and 7 to rebuild:
- `gold_accounts` (account metadata + risk_score, community_id, similarity_score)
- `gold_account_similarity_pairs` (SIMILAR_TO pairs as a Databricks table)

This must complete before the demo notebook can run.

## Step 4 — Run demo notebook and record Criterion B

Configure `SPACE_ID` in `genie_demos/gds_enrichment_closes_gaps.ipynb` if not already set, then run all cells. Record Check 3 same-ring fraction in the table below.

**Pass targets:**
- Check 1 (PageRank precision at top-20): > 70%
- Check 2 (Louvain max ring coverage): > 80%
- Check 3 (Node Similarity same-ring fraction): > 60% (Criterion B)

## Baseline recording table

Fill in after Steps 1–4:

| Metric | Target | Measured | Pass? |
|--------|--------|----------|-------|
| **Graph structure** | | | |
| Account count | 25,000 | | |
| P2P edge count | ~40,000 | | |
| Within-ring density ratio | > 100x | | |
| **PageRank** | | | |
| Top-20 fraud fraction | >= 50% | | |
| Fraud/normal avg ratio | >= 2.0 | | |
| **Louvain** | | | |
| Avg purity across rings | >= 50% | | |
| Min per-ring coverage | >= 80% | | |
| Ring 5 purity (known outlier) | record only | | |
| **Node Similarity — Criterion A** | | | |
| SIMILAR_TO relationship count | ~250,000 | | |
| Fraud avg similarity_score | record only | | |
| Normal avg similarity_score | record only | | |
| Fraud/normal avg ratio | >= 2.0 | | |
| **Node Similarity — Criterion B (demo)** | | | |
| Check 3 same-ring fraction | > 60% | | |
| Check 1 PageRank precision | > 70% | | |
| Check 2 Louvain ring coverage | > 80% | | |

## Research notes — parameter tuning history (2026-04-16)

### What we tried and what we learned

#### GDS-level fixes (did not work)

Two GDS-level fixes were tried before discovering the root cause was in the generator:

**Stale relationship cleanup.** `NodeSimilarity.write` appends `:SIMILAR_TO` edges — it does not replace them. Three successive GDS runs had accumulated 749,970 edges (3× the expected 249,990). Added a Step 5.5 to `run_and_verify_gds.py` that deletes all existing `:SIMILAR_TO` edges before each run. This fixed data hygiene but had zero effect on the fraud/normal ratio (still 1.01×) because the root cause was the noise floor, not stale data.

**`degreeCutoff=5`.** Added to the NodeSimilarity call to exclude accounts with fewer than 5 TRANSACTED_WITH edges. Excluded 734 accounts. Zero effect on ratio (still 1.01×). The noise is from accounts that DO have 5–20 transactions, not from sparse accounts.

#### Root cause: noise floor from small merchant universe

`diagnose_similarity.py` (new script, `finance-genie/validation/`) exposed the problem:

```
Account similarity_score distribution (all accounts):
  avg=0.1415  p10=0.1111  p25=0.1250  p50=0.1364  p75=0.1538  p90=0.1765

Fraud vs normal breakdown:
  fraud:  avg=0.1430  p50=0.1429  max=0.2857
  normal: avg=0.1414  p50=0.1364  max=0.3333
  ratio = 1.01×  FAIL
```

With 2,500 merchants and 25,000 accounts each visiting ~10 merchants, every merchant has ~100 customers. Random coincidental 2-merchant overlap is common (Jaccard ≈ 2/18 ≈ 11–14%), creating a noise floor for ALL accounts at ~0.14. Ring anchor signal was effectively zero — ring-mates never appeared in each other's top-10 SIMILAR_TO because random coincidental pairs scored higher.

#### Hidden .env override discovery

`finance-genie/setup/.env` contained Phase 2 weak-signal parameters that had been overriding `config.py` defaults the entire time:

```
WITHIN_RING_PROB=0.12    # config default: 0.50
RING_ANCHOR_PREF=0.09    # config default: 0.18 (we had set 0.40 in config.py)
RING_ANCHOR_CNT=4        # config default: 5
WHALE_INBOUND=0.20       # config default: 0.10
```

This explained three previously mysterious failures:
- **Node Similarity 1.01×**: `RING_ANCHOR_PREF=0.09` meant ring members visited only ~0.9 of their 4 anchor merchants per account. Two ring-mates shared near-zero anchors.
- **Louvain borderline at 46–50%**: `WITHIN_RING_PROB=0.12` produced only 4,800 within-ring P2P links — thin ring structure.
- **PageRank top-20 fraud fraction = 0%** across all runs: same root cause — rings were too sparse for captains to accumulate enough PR.

When we set `RING_ANCHOR_PREF=0.40` in `config.py`, the .env `RING_ANCHOR_PREF=0.09` silently took precedence. The first regeneration produced correct NUM_MERCHANTS=7500 (not in .env) but wrong anchor preference.

#### WITHIN_RING_PROB=0.50 + CAPTAIN_TRANSFER_PROB=0.10 conflict

Restoring `WITHIN_RING_PROB=0.50` (20,000 within-ring links) combined with the existing `CAPTAIN_TRANSFER_PROB=0.10` over-concentrated inbound on captains:

- `0.10 × 20,000 = 2,000` captain-routed transfers / 50 captains = **40 inbound per captain** from routing alone
- Plus organic ring traffic: ~18 per captain = **~58 total captain inbound**
- Whale avg inbound: **40.4**

Captains beat whales in raw inbound count. `verify_fraud_patterns.py` Check 1 failed: top_200_whales=150, top_200_fraud_members=50.

`CAPTAIN_TRANSFER_PROB=0.10` was set when `WITHIN_RING_PROB=0.12` — it was a compensating boost for sparse rings. With dense rings (0.50), that boost is no longer needed and causes captains to dominate.

#### Final fix: CAPTAIN_TRANSFER_PROB=0.02

At 0.02 with WITHIN_RING_PROB=0.50:
- Captain-routed inbound: `0.02 × 20,000 / 50` = **8 per captain**
- Organic ring inbound: ~20 per ring member
- Captain total: **~28** — comfortably below whale avg 40.4
- Still provides light coordination signal realistic to a real fraud ring hierarchy

All four `verify_fraud_patterns.py` checks pass with this setting. Key numbers vs the old dataset:

| Metric | Old (WITHIN_RING_PROB=0.12) | New | Why it matters |
|--------|----------------------------|-----|----------------|
| Ring density ratio | 862x | **6,428x** | Louvain community detection |
| Within-ring Jaccard | 0.011 | **0.107** | NodeSim ring signal |
| Cross-ring Jaccard | 0.0019 | **0.00056** | NodeSim noise floor |
| Jaccard signal/noise | 6x | **191x** | Headroom for GDS ratio |
| High-risk gap | ~2 pp | **0.55 pp** | Tabular signal stays hidden |
| Top-200 fraud members | 0 | **17** | Ring members lightly visible (realistic) |

The within-ring Jaccard ratio of 191x in the raw CSV (vs the GDS target of 2x) gives very strong confidence the NodeSimilarity ratio will pass after upload. The signal now far exceeds the noise before GDS even runs.

## Decision matrix

### If all checks pass
Update the FIX_DATA.md checklist. Node Similarity work is complete.

### If Criterion A fails (fraud/normal ratio < 2.0)

**Root cause confirmed by `diagnose_similarity.py` (run 2026-04-16):**

Diagnostic output showed all accounts clustering at similarity_score ≈ 0.14 regardless of fraud label:

```
fraud:  avg=0.1430  p50=0.1429  max=0.2857
normal: avg=0.1414  p50=0.1364  max=0.3333
ratio = 1.01×  FAIL
```

The merchant universe (2,500 merchants, 25,000 accounts, ~10 transactions each) is too small — every merchant has ~100 customers on average, so random coincidental 2-merchant overlaps are common. The noise floor (MAX Jaccard for a normal account ≈ 0.14) exceeds the ring signal (avg within-ring Jaccard ≈ 0.011 at RING_ANCHOR_PREF=0.18). Ring-mates never appear in any account's top-10 SIMILAR_TO because random pairs score higher.

**Fix requires two parameter changes — conservative path first:**

| Parameter | Current | Conservative | Validated (fallback) |
|-----------|---------|--------------|---------------------|
| `NUM_MERCHANTS` | 2,500 | 7,500 | 10,000 |
| `RING_ANCHOR_PREF` | 0.18 | 0.40 | 0.50 |

**Why NUM_MERCHANTS matters:** increasing merchants reduces customers-per-merchant (currently 100, target 25–33), which collapses the noise floor by reducing coincidental merchant sharing. This is the primary lever. NUM_MERCHANTS only affects `merchants.csv` (row count grows from 2,500 to 7,500 or 10,000); all other tables are unchanged. This change does not affect Louvain.

**Why RING_ANCHOR_PREF matters:** at 0.18, ring members visit ~1.8 of their 5 anchors on average — too few for two ring-mates to reliably share anchors in their top-10. At 0.40, they visit ~2.8 anchors on average → two ring-mates share ~2–3 anchors (Jaccard ≈ 0.15–0.20), which clears the lower noise floor. This change does not affect Louvain (separate P2P graph).

**Conservative path (try first):**
```
NUM_MERCHANTS=7500
RING_ANCHOR_PREF=0.40
```
Set in `finance-genie/setup/config.py` or `finance-genie/.env`. The expected outcome is noise floor dropping from ~0.14 to ~0.10–0.12, ring signal rising to ~0.15–0.20, giving ratio ~1.5–2.0×. This may not clear 2.0× — if it does not, move to the validated fallback.

**Before regenerating:** run `verify_fraud_patterns.py` after the change to confirm the tabular signal gap (high-risk fraction) stays < 5 pp. At RING_ANCHOR_PREF=0.40, ring members direct 40% of transactions to anchors. If anchors were sampled from high-risk merchants this would widen the gap, but anchors are sampled from all merchants uniformly (`ring_anchors` sampling in `generate_data.py` uses `all_merchant_ids`), so the column signal should be unaffected.

**Validated fallback (if conservative path fails):**
```
NUM_MERCHANTS=10000
RING_ANCHOR_PREF=0.50
```
Analytically gives customers-per-merchant ≈ 25, ring anchor visits ≈ 3.4 of 5 per member, expected ratio ~2.25×. At 0.50 anchor preference, verify that the RING_ANCHOR_PREF check in `verify_fraud_patterns.py` still passes before uploading.

**Full regeneration steps after any parameter change:**
1. Edit `finance-genie/setup/config.py` (or `finance-genie/.env`)
2. `uv run setup/generate_data.py` — regenerates all CSVs
3. `uv run setup/verify_fraud_patterns.py` — confirm column signal gap < 5 pp
4. Re-upload CSVs to Databricks and re-run notebooks 00 and 01
5. Re-run from Step 1 of this plan

### If Criterion B fails (same-ring fraction < 60%) but Criterion A passes
The GDS feature is strong enough but the Genie query is pulling in too many low-scoring pairs, diluting the same-ring fraction. Two likely causes:

**Cause 1 — Genie returns too many rows without a tight LIMIT.** Across all 250k SIMILAR_TO pairs the same-ring fraction is roughly 4% (10,000 ring pairs / 250,000 total). Any unbounded or loosely bounded query will fail at 60%. Check the SQL Genie generated in the demo notebook output. If it lacks a LIMIT or sorts incorrectly, add a Genie Space instruction: "When querying gold_account_similarity_pairs for similar account pairs, always sort by similarity_score descending and limit to 20 results."

**Cause 2 — topK=10 produces too few ring pairs near the top.** Fix: increase topK from 10 to 20 in `run_and_verify_gds.py` Step 6 and the matching cell in `feature_engineering/02_aura_gds_guide.ipynb`. Re-run Step 2, then Step 3, then Step 4. No generator change needed. This doubles the SIMILAR_TO edge count to ~500k and increases ring-pair representation at high similarity scores.

### If PageRank fails (top-20 fraud fraction < 50%)
This is a generator parameter problem, not a Node Similarity problem. The captain topology and reduced whale budgets were intended to fix this. Re-read the PageRank section of FIX_DATA.md and investigate the per-ring diagnostic output from `run_and_verify_gds.py`.

### If Louvain fails (avg purity < 50%)
This would be a regression from the accepted baseline. Investigate whether the new data upload changed anything unexpected in the P2P graph. The Louvain result should be stable if WITHIN_RING_PROB, WHALE_INBOUND, WHALE_OUTBOUND, and CAPTAIN_TRANSFER_PROB are unchanged. Run `validate_neo4j_graph.py` to confirm the graph structure is intact.

## What else needs to be done (full checklist gap)

Beyond Node Similarity, the full path to a passing demo is:

1. **Step 1 above** — `validate_neo4j_graph.py` passes (currently unchecked in FIX_DATA.md)
2. **Step 2 above** — `run_and_verify_gds.py` passes all four checks (currently unchecked)
3. **Step 3 above** — Rebuild gold tables in notebook 03 (not in FIX_DATA.md checklist, but required before the demo)
4. **Step 4 above** — Demo notebook all three checks pass (currently unchecked)
5. **SPACE_ID** — Set `SPACE_ID` in `gds_enrichment_closes_gaps.ipynb` before running it
6. **Genie Space data refresh** — After gold tables are rebuilt, confirm the Genie Space has picked up the new schema for `gold_accounts` and `gold_account_similarity_pairs`; re-run table description generation in the Space settings if not
