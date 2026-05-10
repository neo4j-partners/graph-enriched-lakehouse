# Final Integration Plan

**Goal:** Finish the work needed for the deployed `graph-fraud-analyst` app to run the full demo against real Databricks services (SQL warehouse, Genie Space, Unity Catalog gold tables), with the testing checklist in `apx-demo-client-testing.md` passing end to end.

**Companion docs:**
- `apx-demo-client-testing.md`, Phase 1, 2, 3 walk and Playwright automation.
- `graph-fraud-analyst/CLAUDE.md`, apx conventions and DI rules.
- `graph-fraud-analyst/databricks.yml` and `graph-fraud-analyst/app.yml`, current bundle and resource bindings.

**Deployed URL (current):** https://graph-fraud-analyst-1098933906466604.4.azure.databricksapps.com

---

## Status snapshot at start of this plan

Backend services already call real Databricks APIs:

- `services/rings.py` queries `gold_fraud_ring_communities` via SQL warehouse.
- `services/accounts.py` queries `gold_accounts` via SQL warehouse.
- `services/loader.py` row-counts gold tables for selected ring ids.
- `services/genie.py` calls `ws.genie.start_conversation_and_wait` against the bound Genie Space.

Frontend hooks (`useSearchRingsSuspense`, `useLoadRings`, `useAskGenie`, `useCurrentUserSuspense`) consume the real OpenAPI client at `src/graph_fraud_analyst/ui/lib/api.ts`. There is no mock-service layer to swap.

Deploy state: `graph-fraud-analyst` is `ACTIVE`, deployment `AppDeploymentState.SUCCEEDED`. Gold tables are populated (10 ring candidates). OAuth, OBO, and live smoke against the deployed URL have not been verified.

---

## Checklist

### 1. Deployed-app smoke (manual)

The single highest-value next action. Validates OAuth, resource bindings, SQL warehouse path, Genie path, and the gold-table architecture in one pass.

- [ ] Open the deployed URL in a fresh browser tab; complete the OAuth login.
- [ ] Land on `/`, navigate to `/search`. Confirm the workbench renders with light theme and IBM Plex fonts.
- [ ] **Fraud rings mode**: confirm the table populates from `gold_fraud_ring_communities`. Expect 10 rows (current ring-candidate count). Spot-check that `risk_score`, `member_count`, `topology` look plausible.
- [ ] Toggle **Risky accounts** and **Central accounts** modes. Confirm both return rows from `gold_accounts`.
- [ ] Select two rings, click **Continue to Load**. Confirm `/load` shows real row counts for the three gold tables.
- [ ] Click **Continue to Analyze**. Click a sample question. Confirm the Genie answer renders. Confirm a follow-up question reuses the same `conversation_id` (DevTools network tab).
- [ ] Free-text question through the textarea. Verify Enter submits, Shift+Enter inserts a newline.
- [ ] DevTools console: zero errors, zero React warnings, zero CSP warnings. Zero 404s on fonts or static assets.

### 2. OBO scope wiring (`/api/current-user`)

The `current-user` route in `backend/router.py:26` injects `Dependencies.UserClient`, which is on-behalf-of. The deployed app needs the `user_authorization` scopes declared so it can issue OBO tokens.

- [ ] Verify whether `/api/current-user` returns 200 against the deployed URL. If 200, skip the rest of this section.
- [ ] If 401 or 403: add a `user_authorization:` block to `graph-fraud-analyst/app.yml` with the minimum scopes the route needs (typically `user:read` and the workspace scope). Reference the apx skill docs for the exact YAML shape.
- [ ] Redeploy via `./scripts/deploy.sh`.
- [ ] Re-verify `/api/current-user` returns 200 with the logged-in user's identity.

### 3. Genie Space binding name reconciliation

`databricks.yml` binds the Genie Space resource as `graph-fraud-analyst-genie`. `apx-demo-client-testing.md` (Phase 2.3) references `fraud-signals-genie`. Cosmetic, but the doc should match the code.

- [ ] Update `apx-demo-client-testing.md` so the Genie resource key reads `graph-fraud-analyst-genie`. Also update the warehouse key from `fraud-analyst-warehouse` to `warehouse`.
- [ ] Update the Neo4j secret-scope references in the same section (see item 4).

### 4. Neo4j live integration: keep gold-table path, amend the doc

The testing doc Phase 3 promises "real Neo4j calls" once F11 lands. The backend has zero Neo4j code: no driver import, no `NEO4J_*` binding in `app.yml`, no secret-scope binding in `databricks.yml`. Ring data is read exclusively from the pre-computed `gold_fraud_ring_communities` Delta table populated by the `automated/` pipeline. This matches `demo-client-graph-backend.md` (gold tables as the runtime source of truth).

- [ ] Decision: keep the gold-table-only runtime path. Confirm with the demo owner.
- [ ] Amend `apx-demo-client-testing.md` Phase 3.1 to remove the "real Neo4j" promise. Replace with "real SQL warehouse query against `gold_*` Delta tables".
- [ ] Amend Phase 2.3 to drop the `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` binding requirement.
- [ ] If live Neo4j is actually wanted for the demo, file a separate work item. It is a meaningful addition: driver dependency, secret scope, a `services/neo4j.py` module, a new route, and a UI mode toggle. Out of scope for the "finish" plan.

### 5. Deploy-time logs path (upstream MCP bug, workaround already in place)

The `manage_app(get, include_logs=true)` MCP call surfaces `404 Client Error: Not Found for url: .../api/2.0/apps/{name}/deployments/{id}/logs`. The local patch in `databricks-tools-core/databricks_tools_core/apps/apps.py` fixed the prior `ImportError` but the upstream endpoint path is wrong. CLI log tail still works.

- [ ] Confirm the workaround: `databricks apps logs graph-fraud-analyst --follow --profile azure-rk-knight` streams logs cleanly.
- [ ] (Optional, not strictly required to finish) File an upstream `ai-dev-kit` issue documenting the wrong logs endpoint path and the prior `get_api_client` import bug. Link the local patch as a reference.

### 6. Playwright MCP automation

`apx-demo-client-testing.md` Phase 1.5 and 3.2 describe scripted walkthroughs. None exist in the repo today.

- [ ] Confirm whether scripted Playwright automation is in scope for the demo, or whether the manual walkthrough is sufficient. If the demo is a one-time live event, skip.
- [ ] If in scope: list available Playwright MCP tools at the start of the run (names vary by server build).
- [ ] Write a single script that walks `/search`, `/load`, `/analyze` with accessibility-tree assertions. Save under `graph-fraud-analyst/tests/playwright/`.
- [ ] Run against the deployed URL with the OAuth `storageState` trick (log in once, persist, replay).
- [ ] Bump every `browser_wait_for` by 50 percent for the deployed run vs local.

### 7. F9 ReportModal (Export Report)

Currently a placeholder sonner toast. The doc treats it as not yet built.

- [ ] Confirm whether F9 is in scope for the demo. If the export feature is not part of the live story, leave the toast and remove the export button before recording.
- [ ] If in scope: build the modal per the F9 spec. Plug it into the existing Export Report click handler in `routes/_workbench/analyze.tsx`. Run `apx dev check` and re-test.

### 8. Dead Lakebase scaffolding (cleanup)

The previous "light removal" left `core/lakebase.py` and `Dependencies.Session` in place even though no route or service consumes them. Not blocking, but it is dead code.

- [ ] Confirm with the demo owner whether Lakebase is on the near-term roadmap. If yes, leave the scaffolding. If no, delete `core/lakebase.py`, drop `Dependencies.Session`, remove the `sqlmodel` dep from `pyproject.toml`, run `apx dev check`.

### 9. Final pre-demo verification

Run after every other item above is closed.

- [ ] `apx dev check` returns green (tsc + ty).
- [ ] `./scripts/deploy.sh` exits 0; deploy logs show clean FastAPI startup with zero stack traces.
- [ ] Deployed-app smoke (item 1) passes end to end.
- [ ] Genie returns plausible answers on at least three distinct prompts, including one that produces a table.
- [ ] Browser console clean on the deployed URL across all three screens.
- [ ] OAuth login works from a private browsing window (no cached session).

---

## Out of scope for "finish"

- Real Neo4j live calls (item 4 decision: keep gold-table path).
- Real Lakebase persistence (item 8 decision pending).
- Replacing the demo's pre-computed pipeline with a live recompute path.
- Production observability, alerting, autoscaling tuning.

---

## Effort estimate

| Item | Effort |
| --- | --- |
| 1. Deployed smoke | 15 min |
| 2. OBO scopes (if needed) | 20 min |
| 3. Doc reconciliation | 10 min |
| 4. Neo4j decision + doc amend | 20 min |
| 5. Logs workaround confirm | 5 min |
| 6. Playwright automation | 2 to 4 hours (skip if out of scope) |
| 7. F9 modal | 2 to 3 hours (skip if out of scope) |
| 8. Lakebase cleanup | 20 min |
| 9. Final verification | 30 min |

Minimum path to a working demo: items 1, 2, 3, 4, 9. About 90 minutes if OBO scopes need adding, 60 minutes if they do not.
