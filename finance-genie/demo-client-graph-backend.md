# Fraud Analyst Backend, Data Pipeline Updates

**Companion to:** `demo-client-graph.md` (the APX web app proposal), `automated/README.md` (the existing pipeline)
**Audience:** the agent running parallel to the web app build, working inside `finance-genie/automated/`
**Goal:** make every field the Fraud Analyst web app needs come from real, pipeline-produced data, with one named exception.

---

## Why this document exists

The web app proposed in `demo-client-graph.md` exposes three Screen 1 result types, a Load action, and a Genie ask. Most of what those endpoints return is already produced by the existing pipeline in `automated/`, but a handful of fields either have no source today, are derivable but expensive at query time, or live in flat files that the web service should not be reading directly.

This document locks in, for each field the web app needs, exactly where it comes from. It then lists the small set of additions to `automated/` that turn the locked-in plan into a single clean read path from Unity Catalog. A separate agent is implementing the web app in `finance-genie/apx-demo/` against this contract; do not coordinate file-by-file, just deliver to the contract below.

---

## Locked-in data contract

For every field the web app returns, this table is the binding source-of-truth. Anything marked "real" is data the pipeline produces today or after the work items in this document. Anything marked "substitute" is real data being used in place of a field name that originally implied a different metric, with the substitution called out in the API response and in code comments. Exactly one field is mocked.

### Ring results, Screen 1 mode "Fraud rings"

| Web-app field | Source | Status |
|---|---|---|
| ring_id | gold_fraud_ring_communities.community_id | real |
| node count | gold_fraud_ring_communities.member_count | real |
| volume | new column, gold_fraud_ring_communities.total_volume_usd, summed within-community account-link amounts | real, work item W3 |
| risk band, H/M/L | derived in service from gold_fraud_ring_communities.avg_risk_score | real |
| risk_score | gold_fraud_ring_communities.avg_risk_score | real |
| topology, star/mesh/chain | new column, gold_fraud_ring_communities.topology, classified by within-community degree skew | real, work item W3 |
| shared_identifiers | new column, gold_fraud_ring_communities.anchor_merchant_categories, populated from ground_truth.json anchor_merchants at gold-build time | real, work item W3 |
| graph nodes and edges, for thumbnail | derived in service from a Cypher query that samples up to 12 accounts plus their within-community links | real, no pipeline change |

### Risky account results, Screen 1 mode "Risky accounts"

| Web-app field | Source | Status |
|---|---|---|
| account_id | gold_accounts.account_id | real |
| risk_score | gold_accounts.risk_score | real |
| velocity, Low/Medium/High | new column, gold_accounts.txn_count_30d, binned in the service | real, work item W4 |
| merchant_diversity, Low/Medium/High | new column, gold_accounts.distinct_merchant_count_30d, binned in the service | real, work item W4 |
| account_age_days | derived in service from gold_accounts.opened_date | real, no pipeline change |

### Central account results, Screen 1 mode "Central accounts"

| Web-app field | Source | Status |
|---|---|---|
| account_id | gold_accounts.account_id | real |
| neighbors | new column, gold_accounts.distinct_counterparty_count | real, work item W4 |
| betweenness | new column, gold_accounts.betweenness_centrality | real, work item W1 |
| shortest_paths | mocked in the web service, deterministic value derived from gold_accounts.inbound_transfer_events | mock, only field in the entire app |

The shortest_paths field is the one place the web app does not call out a real number. The choice to mock rather than compute reflects that the value adds visual texture to the Central Accounts table but is never the basis of a downstream decision in the demo. If a future pass adds an All Pairs Shortest Path or a closeness-centrality run to the GDS pipeline, the web service drops the mock without any other change.

### Load results, Screen 2

| Web-app field | Source | Status |
|---|---|---|
| target_tables | static list of the three gold tables | real |
| steps, the 7-step animation | step labels are real names of pipeline stages, the 700ms inter-step timing is UI-side choreography | real labels |
| row_counts | live counts queried from the gold tables, filtered to the selected community_ids | real |
| quality_checks | the 6 checks already implemented in cli/04_validate_gold_tables.py, lifted into a callable module so both the CLI and the web service share them | real, work item W5 |

The Load endpoint never writes anything. The gold tables already exist by the time the web app runs. Screen 2 is a live read of what the pipeline produced, presented as a progress animation.

### Genie ask, Screen 3

| Web-app field | Source | Status |
|---|---|---|
| conversation_id, message_id, text, table | live Genie Conversation API call against the AFTER-GDS Genie Space | real |

The web service ports the Conversation API logic already implemented in `cli/05_genie_run_after.py`. No pipeline change needed.

---

## Work items in `automated/`

Five independent items. Each is sized to land as one commit. The pipeline agent can execute these in any order with one caveat: W1 and W4 both modify the GDS run, so do them in the same pass through `validation/run_gds.py` if convenient, but the column writes are independent and either can ship first.

### W1. Add betweenness centrality to the GDS run

**Why:** The web app's Central Accounts table presents a column named "betweenness." Today the pipeline computes PageRank, Louvain, and Node Similarity, but no betweenness. Without this work item, the web app substitutes PageRank under the betweenness column heading, which is honest but loses the distinct signal that betweenness measures, namely accounts that sit on a lot of paths between other accounts.

**What changes:** Add a Betweenness Centrality call to the existing GDS run in `validation/run_gds.py`, writing the result back to a new property on `:Account` nodes. Use the same write-back pattern the file already uses for PageRank. The chosen algorithm should be the sampled variant if runtime is a concern at the workshop dataset size, otherwise the exact variant. Persist the per-node value to Neo4j and let the existing pull-back step in `cli/03_pull_gold_tables.py` carry it through to a new column on gold_accounts.

**Naming:** the new gold_accounts column is `betweenness_centrality`, double precision, nullable for accounts that fall below the GDS minimum-degree threshold, comment string consistent with the existing risk_score and similarity_score columns.

**Schema work:** add the column to `sql/gold_schema.sql` with an explicit comment matching the style of the existing columns. Update `cli/03_pull_gold_tables.py` to read the new property and write it through. Do not break the column ordering for any column that already exists.

**Validation:** extend `validation/verify_gds.py` to confirm the new property is populated on the same node set as risk_score and that ring members in the ground_truth file score, on average, higher than non-ring accounts. Tolerance can match the existing PageRank check.

### W2. Decide shortest_paths, document, do not implement

**Why:** The web app needs a value to display in the shortest_paths column. The locked-in plan is to mock that one value in the web service. The pipeline does not need to compute anything for this field today, but the decision deserves a worklog entry so a later pass can replace the mock cleanly.

**What changes:** Add a short note to `worklog/` recording that shortest_paths is intentionally mocked in the web layer, that the natural pipeline source is either an All Pairs Shortest Path run or closeness centrality, and that whichever lands first should be written to a new gold_accounts column with a similar shape to W1. No code change.

**Validation:** none.

### W3. Add ring-level rollup columns

**Why:** The web app's Ring Results view displays ring volume, ring topology, and a list of shared identifiers per ring. None of these are in `gold_fraud_ring_communities` today. Computing them at query time is possible but slow and forces the web service to either join `account_links` on every Screen 1 load or read the `ground_truth.json` file directly. Better to add them once at gold-build time.

**What changes:** Three new columns on `gold_fraud_ring_communities`.

The first new column is `total_volume_usd`, double precision. It is the sum of `account_links.amount` for every link whose source and destination both belong to this community. Account-to-account transfers only; do not include merchant transactions. The intent is to surface the internal P2P flow that is the on-message fraud-ring signal, the cycling of money through a closed group of accounts. Merchant spend by ring members is cover behavior and would dilute the figure with everyday transactions unrelated to the ring claim. Anchor merchants are represented separately via the `anchor_merchant_categories` column below, so no signal is lost. Compute it in `jobs/03_pull_gold_tables.py` via a Spark aggregation joined on `gold_accounts.community_id` so it stays consistent with however the gold accounts table classifies membership.

The second new column is `topology`, string, one of `star`, `mesh`, or `chain`. Classify each community by its within-community degree distribution. The simple, deterministic rule, which matches the visual intent of the wireframe: compute each member's within-community degree, then take the ratio of the highest-degree member to the average degree. If that ratio is greater than three, classify as star. Otherwise compute the edge density, defined as actual within-community links divided by maximum possible links. If density is greater than 0.15, classify as mesh. Otherwise classify as chain. Thresholds may need tuning once you see the actual distribution in the workshop dataset; treat the numbers as starting points and adjust by inspection so each ring lands in a defensible bucket.

The third new column is `anchor_merchant_categories`, array of strings. The mapping from ground-truth ring_id to Louvain community_id is the `ring_community_map.json` file already written by `jobs/03_pull_gold_tables.py`, which records one ring as a list of community_ids because Louvain can split a single ground-truth ring across multiple communities. For each ring in that map, attach the four anchor merchant categories from `data/ground_truth.json` to every community_id in the ring's list, not only the dominant one. All such communities are, by the pipeline's own accounting, part of the same fraud ring; tagging only the dominant community would arbitrarily privilege one Louvain output and would hide the over-segmentation rather than show it. Write the categories as a string array in the order they appear in ground_truth. Communities that do not appear in any ring's list get null. The web app filters to `is_ring_candidate = true` for the rings view, so any non-candidate community that happens to be tagged will not surface in the UI regardless; if multiple candidate communities for the same ring do surface, the analyst correctly reads the duplicated anchor categories as a Louvain split.

**Schema work:** add all three columns to `sql/gold_schema.sql` with comments. Update `cli/03_pull_gold_tables.py` to compute and write them. Keep existing columns and their order unchanged.

**Validation:** extend `validation/04_validate_gold_tables.py` with three new checks. The first asserts total_volume_usd is positive for every ring-candidate community. The second asserts topology is non-null and one of the three allowed values for every ring-candidate community. The third asserts anchor_merchant_categories has length 4 for every community whose community_id maps to a ground-truth ring.

### W4. Add per-account behavior columns

**Why:** Screens 1 mode "Risky accounts" needs velocity and merchant_diversity per account. Screen 1 mode "Central accounts" needs a neighbors count. Today these would all be computed from raw `transactions` and `account_links` at query time, which forces the web service to issue costly aggregations on every page render. Better to precompute.

**What changes:** Three new columns on `gold_accounts`.

The first new column is `txn_count_30d`, big integer. It is the number of rows in `transactions` for this account_id whose `txn_timestamp` falls within the most recent 30 days of the dataset. Compute it in `cli/03_pull_gold_tables.py` via a Spark window over `transactions`.

The second new column is `distinct_merchant_count_30d`, big integer. It is the count of distinct `merchant_id` values across the same 30-day window for this account.

The third new column is `distinct_counterparty_count`, big integer. It is the count of distinct accounts this account either sent funds to or received funds from across the entire `account_links` window. Pull both directions, union, count distinct, write per source account_id.

**Schema work:** add all three columns to `sql/gold_schema.sql` with comments. Update `cli/03_pull_gold_tables.py` accordingly.

**Validation:** extend `validation/04_validate_gold_tables.py` with two new checks. The first asserts the three new columns are non-negative integers. The second asserts that, on the workshop dataset, the average distinct_counterparty_count for ring-member accounts is materially higher than for non-ring accounts, since ring members by construction transact within the ring. Use the existing ground_truth file to define the two cohorts.

### W5. Lift the gold-table validation checks into a shared module

**Why:** Screen 2 of the web app shows a list of quality checks running. The honest demo is that those checks are the real checks the pipeline runs after producing the gold tables. Today those checks live inline inside `cli/04_validate_gold_tables.py` as a script. The web service needs to call the same logic from a process other than that script, so the checks must be lifted into an importable module and called from both places.

**What changes:** Create a new module under `automated/` that exposes a single function whose return type is a list of named check results, each with a name, a passed boolean, and a free-text detail string. The existing `cli/04_validate_gold_tables.py` becomes a thin wrapper around that module that prints results and exits non-zero on failure. The web app imports the same module and renders the result list in Screen 2.

The check names returned by the module should match the friendly labels currently printed in `cli/04_validate_gold_tables.py`, since those labels appear in the wireframe directly. If the existing labels are terse, expand them to short readable phrases, then update both the CLI output and the wireframe-side rendering to use the new labels.

**Validation:** confirm the existing CLI behavior is unchanged by running `python -m cli submit 04_validate_gold_tables.py` against the workshop dataset and comparing output to the pre-change run.

---

## Validation that does not require the web app

Each work item above is fully validatable without the web app being available. The pipeline agent confirms their work by:

- running `setup/generate_data.py` if needed to refresh the local CSVs
- running `./upload_and_create_tables.sh` to refresh the base UC tables
- submitting `02_neo4j_ingest.py`, `validation/run_gds.py`, `validation/verify_gds.py`, `cli/03_pull_gold_tables.py`, `cli/04_validate_gold_tables.py` in order
- verifying every new column is populated on the expected row set, with values in the expected ranges
- spot-checking three random ring communities by hand against the ground_truth file

The web app agent will pick up the new columns automatically once they land in Unity Catalog. There is no API surface to coordinate.

---

## Hand-off boundary, what the pipeline agent should not touch

- The web app code in `finance-genie/apx-demo/`. The web app agent owns that directory.
- The Pydantic models in `apx-demo/src/fraud_analyst/backend/models.py`. Field names there are the contract; the pipeline agent does not edit them, only delivers data that fits.
- The wireframe assets in `finance-genie/fraud-analyst.md` and the design bundle. Visual decisions live with the web app agent.
- Workspace-level config in `app.yml` and `databricks.yml` inside `apx-demo/`. The pipeline does not affect deploy targets.
- The Genie Space provisioning. Existing Genie Spaces are sufficient for the web app's `/api/genie/ask` endpoint. The pipeline agent does not need to add or modify spaces.

If the pipeline agent finds that a work item above forces a change in the web-app-owned files, stop and raise it. The contract above is meant to be sufficient; if it is not, the contract changes first, then the implementations follow.

---

## Order of operations across both agents

The web app agent starts with mock services that return canned data shaped exactly like the locked-in contract above. By the time the pipeline agent finishes W1, W3, W4, and W5, the web app's mock services are ready to be swapped one at a time for real reads, and each swap is a small isolated change. Neither agent blocks the other at any point.

Genie Q&A is real from the first day, since the existing AFTER-GDS Genie Space is already populated.

The single mocked field, `HubAccountOut.shortest_paths`, ships as a mock and stays a mock until W2's recommendation is acted on in a future session.
