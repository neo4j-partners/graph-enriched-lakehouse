# Neo4j Integration Plan

**Goal:** Turn the deployed `graph-fraud-analyst` app into a true Neo4j-backed demo. Search reads live Cypher against Aura, Load materializes a real subgraph from Neo4j into Delta on demand, and `enrichment-pipeline/` shrinks to a one-shot setup step that ingests CSV into Neo4j and runs GDS (Louvain, PageRank, Betweenness) inside Neo4j to persist node properties.

**Aura instance:** `neo4j+s://0582a1b1.databases.neo4j.io` (already referenced in `finance-genie/.env`).

**Companion docs:**
- `final-integration.md`, status of the prior phase (deployed app on SQL warehouse + Genie).
- `apx-demo-client-testing.md`, end-to-end manual and Playwright test plan.
- `graph-fraud-analyst/CLAUDE.md`, apx project conventions.
- `enrichment-pipeline/README.md`, the data pipeline that today produces gold Delta tables.
- `enrichment-pipeline/validation/run_gds.py`, the GDS write script we will promote to the official setup step.

---

## Target architecture

```
SETUP (offline, one-time per demo)
─────────────────────────────────────────────────────────────────────────────
enrichment-pipeline/
  setup/ingest_to_neo4j.py            CSV → Aura (:Account, :Merchant nodes,
                                       TRANSACTED_WITH, TRANSFERRED_TO rels)
  setup/run_gds.py                    Aura-side GDS write:
                                       • gds.louvain.write      → community_id
                                       • gds.pageRank.write     → pagerank
                                       • gds.betweenness.write  → betweenness_centrality
  jobs/03_pull_gold_tables.py         OPTIONAL, flag-gated. Only run if you
                                       want a Delta snapshot for a Genie
                                       quickstart that does not require a
                                       prior Load action.

RUNTIME (deployed Databricks App)
─────────────────────────────────────────────────────────────────────────────
Screen 1, Search:
  services/rings.py     Live Cypher: ring-candidate communities ordered by
                        avg pagerank, filtered by member_count, anchor merchant
                        categories aggregated from member transactions.
  services/accounts.py  Live Cypher: risky accounts ordered by pagerank,
                        central accounts ordered by betweenness_centrality.

Screen 2, Load:
  services/loader.py    Live Cypher pulls the selected community_ids and
                        their edges from Neo4j. Backend converts to a Spark
                        DataFrame (via the SDK) and writes per-session
                        materialized Delta tables in UC for Genie to read.
                        Each step the UI animates corresponds to a real
                        operation (Cypher fetch, schema apply, MERGE INTO,
                        quality checks, etc.).

Screen 3, Analyze:
  services/genie.py     Unchanged. Genie Space queries the materialized
                        Delta tables produced by the Load step.
```

GDS is still in `enrichment-pipeline/`. It is **optional from every script that does not need it**, and the heavy step (running Louvain/PageRank/Betweenness) is a one-shot setup before the demo, not part of the request path.

---

## Live status

**Last updated:** 2026-05-11, after Phase 6 deploy completed and lifespan verified.

| Phase | State |
| --- | --- |
| 0. Pre-flight: Aura reachability and secrets | **Done.** `neo4j-graph-engineering` scope verified, app SP granted READ. Local connectivity to Aura verified. |
| 1. Pipeline reshape (optional GDS, promoted setup script) | **Done.** Created `enrichment-pipeline/setup/run_gds.py` with idempotency check, delegating to `validation/run_gds.py`. Updated `enrichment-pipeline/README.md` to mark `03_pull_gold_tables.py` as optional and call out the new setup step. |
| 2. Backend Neo4j client and config | **Done.** Added `neo4j>=5.20.0` dep, extended `AppConfig` with NEO4J_* fields, implemented `_Neo4jDriverDependency` lifespan, exposed `Dependencies.Neo4j`, declared the three secrets as app resources in `databricks.yml` and bound them in `app.yml` via `valueFrom`. |
| 3. Service rewrites (rings, risky, hubs) | **Done.** `services/rings.py` and `services/accounts.py` rewritten to use live Cypher. `router.py` updated to inject `Dependencies.Neo4j`. OpenAPI response shapes unchanged. |
| 4. Real Load materialization (Cypher → Delta) | **Done.** `services/loader.py` rewritten to pull selected community subgraph from Neo4j, then `CREATE OR REPLACE TABLE ... USING DELTA AS SELECT * FROM VALUES (...)` for the three target tables via the SQL warehouse. Real quality checks against the loaded data. |
| 5. UC table strategy for Genie | **Done.** Decision: reuse `gold_*` table names; each Load overwrites. Granted app SP `CREATE TABLE` and `MODIFY` on the schema. |
| 6. Deploy and live verification | **Done (lifespan + Cypher).** Deploy `01f14cd25d9d1e11ae4f82cb925385a4` and later `01f14cd2*` succeeded; both uvicorn workers report "Application startup complete", which means the Neo4j lifespan's `verify_connectivity()` against Aura passed (Databricks Apps egress to `neo4j+s://0582a1b1.databases.neo4j.io:7687` is open). The three production Search Cypher queries (rings, risky, hubs) and the three Load Cypher queries (accounts, communities, similarity) were each run against Aura using the exact strings in the deployed code: all return correct row counts (10 rings, 5 risky, 5 hubs, 241 accounts for a 2-ring Load, 2 communities, 2000 capped similarity edges) and hit warm latency under 250 ms per query. Browser-side smoke pending. |
| 7. Docs and cleanup | **Done.** Updated `graph-fraud-analyst/README.md` (new architecture summary, step-4 secret-scope ACL, step-5 GDS setup, step-6 prerequisites), `CLAUDE.md` Dependencies table, `apx-demo-client-testing.md` Phase 3.1 (real-Neo4j assertions and latency budgets). `enrichment-pipeline/README.md` marks `03_pull_gold_tables.py` as optional and documents the new `setup/run_gds.py` entry point. |

---

## Checklist

### Phase 0. Pre-flight, Aura reachability and secrets

- [ ] Confirm Databricks Apps egress can reach `0582a1b1.databases.neo4j.io:7687` (bolt+s). If it cannot, file a network change request before doing anything else. Without egress, every other step is wasted.
- [ ] Create or confirm a UC secret scope named `neo4j-graph-engineering` (already referenced by `enrichment-pipeline/jobs/_neo4j_secrets.py` and by `finance-genie/setup_secrets.sh`).
- [ ] Populate the scope with three keys: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`. Use the values currently in `finance-genie/.env`.
- [ ] Grant the app SP `READ` on the secret scope (`databricks secrets put-acl --scope neo4j-graph-engineering --principal <app_sp_client_id> --permission READ`).
- [ ] Verify locally: `apx dev start` then hit a stub route that calls `driver.verify_connectivity()` once. If TLS or auth fails locally, fix before touching the deployed app.

### Phase 1. Pipeline reshape

Goal: keep `enrichment-pipeline/` for the offline setup, make GDS opt-in elsewhere, and promote the existing GDS write script to a first-class setup step.

- [ ] Audit every script in `enrichment-pipeline/jobs/` and `enrichment-pipeline/validation/` for GDS calls. The known callsites are `02_neo4j_ingest.py` (currently writes nodes/rels only, no GDS yet), `validation/run_gds.py` (full GDS write), `validation/verify_gds.py`, `validation/diagnose_similarity.py`.
- [ ] Add a `--with-gds` / `--no-gds` flag (or `RUN_GDS=false` env var) to every script that touches GDS. Default to off everywhere except the dedicated setup script. The point: re-running `02_neo4j_ingest.py` or `03_pull_gold_tables.py` for any reason must never invalidate node properties unless the operator explicitly asks for it.
- [ ] Promote `enrichment-pipeline/validation/run_gds.py` to a setup script. Move (or symlink) it to `enrichment-pipeline/setup/run_gds.py`. Update its docstring to call it "the official one-shot GDS setup step required before running the deployed `graph-fraud-analyst` app".
- [ ] Confirm the script writes these node properties on `:Account`:
  - `community_id` (from `gds.louvain.write`)
  - `pagerank` (from `gds.pageRank.write`)
  - `betweenness_centrality` (from `gds.betweenness.write`)
- [ ] Add a `risk_score` write to the same script. The current pipeline derives `risk_score ≈ pagerank` (see `enrichment-pipeline/jobs/03_pull_gold_tables.py` line 333). The cleanest path is to alias: `MATCH (a:Account) SET a.risk_score = a.pagerank`. If a more sophisticated formula is wanted, port the Spark version inline as a Cypher `SET`.
- [ ] Add an idempotency check at the top of the setup script: refuse to overwrite existing properties unless `--force` is passed, so an accidental re-run does not blow away tuned values.
- [ ] Mark `03_pull_gold_tables.py` as optional in `enrichment-pipeline/README.md`. The live app no longer requires those Delta tables; they only exist for the Genie quickstart scenario or as a fallback if Neo4j is unreachable.
- [ ] Smoke run the setup end-to-end: `02_neo4j_ingest.py` (ingest), then `setup/run_gds.py` (GDS write), then `MATCH (a:Account) RETURN a.account_id, a.community_id, a.pagerank, a.betweenness_centrality, a.risk_score LIMIT 5` to confirm all four properties are present and non-null.

### Phase 2. Backend Neo4j client and config

- [ ] Add `neo4j>=5.20.0` to `graph-fraud-analyst/pyproject.toml` dependencies. Run `uv sync`.
- [ ] Extend `graph_fraud_analyst/backend/core/_config.py::AppConfig` with three fields: `neo4j_uri: str = Field(default="", alias="NEO4J_URI")`, `neo4j_username: str`, `neo4j_password: str`. Use `validation_alias` not the `GRAPH_FRAUD_ANALYST_` prefix because the secret-scope keys are unprefixed.
- [ ] Create `graph_fraud_analyst/backend/core/_neo4j.py`. Implement `_Neo4jDependency(LifespanDependency)` with an async lifespan that creates a `neo4j.AsyncDriver`, calls `verify_connectivity()` once at startup, and stows it on `app.state.neo4j_driver`. On shutdown, `await driver.close()`.
- [ ] Expose `Dependencies.Neo4j: TypeAlias = ...` returning an `AsyncSession` per request. Document in `graph_fraud_analyst/CLAUDE.md` Dependencies table.
- [ ] Bind the three secrets in `graph-fraud-analyst/app.yml`:
  ```yaml
  - name: NEO4J_URI
    valueFrom: "neo4j-graph-engineering/NEO4J_URI"
  - name: NEO4J_USERNAME
    valueFrom: "neo4j-graph-engineering/NEO4J_USERNAME"
  - name: NEO4J_PASSWORD
    valueFrom: "neo4j-graph-engineering/NEO4J_PASSWORD"
  ```
  Use the actual Apps secret-binding YAML once the format is confirmed; the apx skill docs have the exact shape.
- [ ] Confirm `app.yml` env validation by running `apx dev check` (it does not boot the app but catches schema typos).

### Phase 3. Service rewrites

- [ ] Rewrite `services/rings.py::list_rings` to issue Cypher instead of SQL. Suggested query shape:
  ```cypher
  MATCH (a:Account)
  WHERE a.community_id IS NOT NULL
  WITH a.community_id AS community_id,
       count(a)                                    AS member_count,
       avg(a.pagerank)                             AS avg_risk_score,
       collect(DISTINCT a.merchant_category)[0..3] AS anchor_merchant_categories
  WHERE member_count BETWEEN 3 AND $max_nodes
  RETURN community_id, member_count, avg_risk_score, anchor_merchant_categories
  ORDER BY avg_risk_score DESC
  LIMIT 20
  ```
  Topology classification (`star` vs `mesh` vs `chain`) can stay client-side, or move to a second Cypher pass per top community.
- [ ] Rewrite `services/accounts.py::list_risky_accounts` to issue Cypher:
  ```cypher
  MATCH (a:Account)
  WHERE a.pagerank IS NOT NULL
  RETURN a.account_id    AS account_id,
         a.pagerank      AS risk_score,
         coalesce(a.txn_count_30d, 0)            AS txn_count_30d,
         coalesce(a.distinct_merchant_count_30d, 0) AS distinct_merchant_count_30d,
         a.opened_date   AS opened_date
  ORDER BY a.pagerank DESC
  LIMIT $row_limit
  ```
  Note: `txn_count_30d` and `distinct_merchant_count_30d` may not exist as node properties today. Either compute them in the setup step (a Cypher aggregation that writes them as properties) or compute them in this query (more expensive, but acceptable for 25-row demo scale).
- [ ] Rewrite `services/accounts.py::list_central_accounts` to issue Cypher:
  ```cypher
  MATCH (a:Account)
  WHERE a.betweenness_centrality IS NOT NULL
  OPTIONAL MATCH (a)-[r:TRANSFERRED_TO]-(b:Account)
  WITH a, count(DISTINCT b) AS neighbors,
       count(r) AS inbound_transfer_events
  RETURN a.account_id              AS account_id,
         a.betweenness_centrality  AS betweenness,
         neighbors,
         inbound_transfer_events
  ORDER BY betweenness DESC
  LIMIT $row_limit
  ```
- [ ] Add a thin `services/_neo4j_helpers.py` for shared concerns: connection pooling assertions, retry on transient `Neo4jError`, normalization of records to plain dicts.
- [ ] Type checks: `apx dev check` must stay green after each rewrite.
- [ ] Local manual smoke against Aura: hit each rewritten endpoint via `apx dev start`, confirm 200s and that the response shape matches the existing OpenAPI client (no frontend changes needed).

### Phase 4. Real Load materialization (Cypher → Delta)

This is the highest-effort phase. The Load screen stops being a row-count display and becomes a real ETL action.

- [ ] Decide schema for the per-session materialized tables. Options:
  - Reuse `gold_accounts` / `gold_fraud_ring_communities` / `gold_account_similarity_pairs`. Pro: Genie Space already targets them. Con: every Load overwrites the previous session's data; concurrent demos break each other.
  - Introduce `loaded_subgraph_accounts`, `loaded_subgraph_communities`, `loaded_subgraph_edges` tables. Pro: clean separation. Con: Genie Space needs to be repointed to them.
  - Per-user namespaced tables (e.g. `loaded_subgraph_accounts__<user_hash>`). Pro: concurrent demos work. Con: cleanup logic, Genie Space configuration complexity.
- [ ] Recommended choice for a one-presenter demo: reuse the existing `gold_*` table names, but rewrite (not append) on each Load. The seven animated steps map to real operations: Cypher fetch communities, Cypher fetch members, Cypher fetch edges, write three Delta tables via `ws.statement_execution.execute_statement` with `CREATE OR REPLACE TABLE ... AS SELECT ... FROM VALUES (...)`, run quality checks, surface results.
- [ ] Rewrite `services/loader.py::load_rings`:
  - Run Cypher against the selected `community_id` values to pull `:Account` and edges.
  - Convert records to a flat list of dicts.
  - Build a `CREATE OR REPLACE TABLE ... AS SELECT * FROM (VALUES ...)` statement for each of the three target tables. Use `StatementParameterListItem` if rows are small, else stage to a UC volume first and `CREATE TABLE ... USING DELTA LOCATION ...`.
  - For datasets bigger than ~5k rows, use the SDK's `files_api.upload` to a UC volume + `COPY INTO`. Below that threshold, inline VALUES is simpler.
  - Return the same `LoadOut` shape the frontend already expects (steps, row_counts, quality_checks).
- [ ] Update `services/loader.py::_quality_check_labels` so the labels reflect real checks (row-count >0, no nulls in primary keys, community membership matches counts). Wire each label to a real Cypher or SQL assertion.
- [ ] Decide what happens when Load is invoked without a prior setup run (no GDS properties exist in Neo4j). Two options: fail fast with a clear error, or fall back to a "raw" subgraph extraction without risk scoring. Prefer fail-fast for the demo; the failure message should say "Run `enrichment-pipeline/setup/run_gds.py` first".

### Phase 5. UC table strategy for Genie

- [ ] Confirm the Genie Space (id from `GRAPH_FRAUD_ANALYST_GENIE_SPACE_ID`) is configured to read from whichever tables Phase 4 chose. If the choice was "reuse gold_*", no Genie config change. If "loaded_subgraph_*", update the Genie Space data sources and instructions.
- [ ] Verify Genie's sample-question library still produces sensible answers against the new data shape. Most ring-related questions ("which accounts are in the largest ring") translate directly; some account-detail questions may need rephrasing if column names changed.
- [ ] If `03_pull_gold_tables.py` is no longer run by default, decide who is responsible for guaranteeing the gold tables exist when the app first boots (before any user has clicked Load). Options:
  - Ship a deploy-time bootstrap that materializes empty tables with the right schema, so Genie does not 500 on an empty space.
  - Require the operator to run Load at least once before demoing.
  - Run `03_pull_gold_tables.py` once during setup as a "seed" step (flag-gated, default on for the first setup, off for subsequent runs).

### Phase 6. Deploy and live verification

- [ ] `apx dev check` green.
- [ ] `./scripts/deploy.sh` from `graph-fraud-analyst/`. Confirm deploy logs show the Neo4j driver lifespan reporting `Connectivity verified to neo4j+s://0582a1b1.databases.neo4j.io` on startup.
- [ ] Tail `databricks apps logs graph-fraud-analyst --follow` during the smoke walk.
- [ ] Browser smoke through Search → Load → Analyze:
  - Search rings: confirm rows come from Aura (`community_id` should match what `MATCH (a:Account) RETURN DISTINCT a.community_id` returns).
  - Risky accounts: top-25 should match `MATCH (a:Account) RETURN a.account_id ORDER BY a.pagerank DESC LIMIT 25`.
  - Central accounts: top-25 should match the same Cypher with `a.betweenness_centrality`.
  - Load: pick two rings, click through. Confirm a SQL query against UC right after the Load returns the just-written rows (`SELECT count(*) FROM gold_accounts WHERE community_id IN (...)`).
  - Analyze: ask Genie a question that references the loaded communities; verify the table attachment cites the newly-written rows.
- [ ] Latency check: each Cypher round-trip should land under 1.5 s warm. Tune Aura tier if the demo flow feels sluggish.
- [ ] Re-run the smoke 2 to 3 times. The first run pays the driver warmup cost; subsequent runs should feel snappy.

### Phase 7. Docs and cleanup

- [ ] Update `graph-fraud-analyst/README.md`:
  - Step 3 (UC grants) keeps the warehouse grants but adds the Aura secret-scope ACL grant for the app SP.
  - New step 3.5 (or 4) "Run the one-shot Neo4j setup" pointing at `enrichment-pipeline/setup/run_gds.py`.
  - Prerequisites section adds "Neo4j Aura instance reachable and populated".
- [ ] Update `graph-fraud-analyst/CLAUDE.md` Dependencies table to include `Dependencies.Neo4j`.
- [ ] Update `apx-demo-client-testing.md` Phase 3.1 to add specific "real Neo4j" assertions (now true): top-of-list ring `community_id` matches Aura, top-of-list pagerank account matches Aura, latency budgets.
- [ ] Update `enrichment-pipeline/README.md`:
  - Describe the new optional flags for GDS.
  - Document `setup/run_gds.py` as the official one-shot setup step.
  - Reduce emphasis on the gold tables; they are now an optional artifact, not a runtime requirement.
- [ ] Move this plan's Phase 0–7 outcomes back into `final-integration.md` as a closed phase, with a one-line link forward to whatever the next demo capability adds.
- [ ] Optional cleanup: if no script in the codebase still imports the `databricks-tools-core` Lakebase helpers, delete that import path entirely. Out of scope unless it surfaces during the work.

---

## Risks and watchouts

- **Aura egress.** Databricks Apps run in an isolated network. If outbound TLS to `0582a1b1.databases.neo4j.io:7687` is blocked, the entire integration cannot work. Verify in Phase 0 with a `verify_connectivity` call from a deployed test app before doing Phase 2 onward.
- **GDS rerun cost.** Re-running Louvain/PageRank/Betweenness on a fresh ingest of 25k accounts takes a few minutes on a Small Aura tier. The setup script's idempotency check matters: re-running by accident should be a no-op, not a 5-minute recompute.
- **Live latency.** Aura cold cache: 1 to 3 s for the first query. Warm: 200 to 600 ms. The demo should rehearse the warmup hits before the audience watches.
- **Demo determinism.** Live ranking can shift if the underlying data changes. Snapshot the Aura DB before a presentation; restore from snapshot afterward to guarantee the same numbers.
- **Concurrency on Load.** If two analysts run Load simultaneously and the strategy is "rewrite gold_*", they corrupt each other's session. The single-presenter mitigation is fine for now; per-user namespacing is the upgrade path.
- **Genie freshness.** Genie caches its schema view of the underlying tables. After the first Load, the answers should be fresh; the very first Genie query after deploy might use stale schema if the Space was configured against an older catalog. Refresh the Space's data context once after each schema change.
- **Secret scope ACL.** The bind-and-grant flow for `neo4j-graph-engineering` is not the same as UC grants. The app SP needs `READ` on the scope, not on the catalog. Easy to confuse.

---

## Effort estimate

| Phase | Effort |
| --- | --- |
| 0. Pre-flight | 1 hour |
| 1. Pipeline reshape | 3 hours |
| 2. Backend Neo4j client | 2 hours |
| 3. Service rewrites | 3 to 4 hours |
| 4. Real Load materialization | 4 to 6 hours |
| 5. UC table strategy | 1 to 2 hours |
| 6. Deploy and live verification | 1 to 2 hours |
| 7. Docs and cleanup | 2 hours |

Total: roughly 1.5 to 2 demo-days for one developer focused on this work. Phase 4 is the unknown; if the materialization path turns out to need a volume staging plus `COPY INTO`, add half a day.

---

## Out of scope (intentional)

- Replacing the existing Aura instance with a self-hosted Neo4j cluster.
- Live GDS at request time (Louvain on demand). The setup-step pre-compute is the right answer for a demo and keeps response latencies predictable.
- Per-user concurrent demos. Single-presenter is the target.
- Removing Delta entirely. Genie still needs UC tables; the Load step is the bridge.
- Production hardening: graceful degradation when Aura is down, retry budgets, observability/alerts.

---

## Decision log

| Decision | Rationale |
| --- | --- |
| Keep GDS in `enrichment-pipeline/`, make it optional everywhere else | Lets the pipeline keep producing the gold-table snapshot when needed (Genie quickstart, fallback if Aura is down) without forcing GDS to run on every pipeline trigger. |
| Run Louvain/PageRank/Betweenness as a one-shot setup step | Live GDS at request time is slow and non-deterministic. Pre-compute is fast, reproducible, and matches how production graph apps actually behave. |
| Live Cypher for Search, real materialization for Load, unchanged Genie for Analyze | Best demo narrative: "we have live graph data in Neo4j → user finds patterns with live Cypher → user materializes the subgraph into the lakehouse → user chats with Genie about it." Each screen does something real. |
| `risk_score = pagerank` (alias in the setup step) | The current pipeline already treats them as equivalent (`03_pull_gold_tables.py` line 333). Keeping the alias avoids re-implementing a custom risk formula in two places. |
| Single Aura instance (`neo4j+s://0582a1b1...`) for both local dev and the deployed app | One source of truth, one snapshot to manage. Cost is shared. |
