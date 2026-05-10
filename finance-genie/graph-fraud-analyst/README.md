# graph-fraud-analyst

The Fraud Signal Workbench. A Databricks App built with [apx](https://github.com/databricks-solutions/apx) (FastAPI + React) that surfaces ring-candidate communities, risky accounts, and central hub accounts from the gold tables produced by `../automated/`, then lets an analyst load a subgraph and chat with Genie about it.

## Quick start: deploy to Databricks

The fastest path to a live demo.

### 1. Configure

The whole `finance-genie` repo shares a single `.env` at the repo root. If it does not exist yet, copy the sample and fill in values:

```bash
cp ../.env.sample ../.env
```

Required values for this app (already documented in `../.env.sample` under the `apx-demo / graph-fraud-analyst` section, plus the workspace block at the top):

| Variable | Description |
| --- | --- |
| `DATABRICKS_PROFILE` | Profile name from `~/.databrickscfg`. |
| `GRAPH_FRAUD_ANALYST_WAREHOUSE_ID` | SQL warehouse the FastAPI service uses to query gold tables. |
| `GRAPH_FRAUD_ANALYST_GENIE_SPACE_ID` | Genie Space ID for the AFTER-GDS conversational experience. |
| `GRAPH_FRAUD_ANALYST_CATALOG` | Unity Catalog catalog (default `graph-enriched-lakehouse`). |
| `GRAPH_FRAUD_ANALYST_SCHEMA` | Unity Catalog schema (default `graph-enriched-schema`). |

If you are also running the wider finance-genie demo, see `../setup_secrets.sh` for provisioning Neo4j / Genie / MCP secret scopes. That script is not required for this app alone, which uses OAuth via the service principal.

### 2. Deploy

```bash
./scripts/deploy.sh
```

The script sources `.env`, validates the required IDs, then runs two CLI calls:

1. `databricks bundle deploy` uploads the build, creates the app resource, and attaches the warehouse and Genie Space from `databricks.yml`.
2. `databricks bundle run graph-fraud-analyst-app` pushes the uploaded source to the app's compute and starts uvicorn.

`bundle deploy` alone leaves the app `UNAVAILABLE`. The `bundle run` step is what makes the URL serve traffic, so both must succeed.

To deploy and stream live app logs in the same shell:

```bash
./scripts/deploy.sh --log
```

That runs both steps above and then tails `databricks apps logs graph-fraud-analyst --follow` until you ctrl-c.

### 3. Grant Unity Catalog access to the app service principal

The first deploy auto-provisions a service principal for the app (display name `app-XXXXXX graph-fraud-analyst`). The SQL warehouse runs every backend query as that SP, not as the logged-in user, so it needs Unity Catalog grants on the gold-table schema. Without these grants the `/api/search/*` and `/api/load` endpoints return 500 with `[INSUFFICIENT_PERMISSIONS] User does not have USE CATALOG on Catalog 'graph-enriched-lakehouse'`.

Find the SP's `service_principal_client_id` once:

```bash
databricks apps get graph-fraud-analyst --profile "$DATABRICKS_PROFILE" \
  | grep service_principal_client_id
```

Then run these three statements against the warehouse (substitute the client_id):

```sql
GRANT USE CATALOG ON CATALOG `graph-enriched-lakehouse`
  TO `<service_principal_client_id>`;
GRANT USE SCHEMA  ON SCHEMA  `graph-enriched-lakehouse`.`graph-enriched-schema`
  TO `<service_principal_client_id>`;
GRANT SELECT      ON SCHEMA  `graph-enriched-lakehouse`.`graph-enriched-schema`
  TO `<service_principal_client_id>`;
```

CLI equivalent:

```bash
databricks sql query \
  --warehouse-id "$GRAPH_FRAUD_ANALYST_WAREHOUSE_ID" \
  --profile "$DATABRICKS_PROFILE" \
  --query "GRANT USE CATALOG ON CATALOG \`graph-enriched-lakehouse\` TO \`<client_id>\`"
```

Verify:

```sql
SHOW GRANTS `<service_principal_client_id>`
  ON SCHEMA `graph-enriched-lakehouse`.`graph-enriched-schema`;
```

You should see at least `SELECT` and `USE SCHEMA` rows. The grant is per workspace, so it only needs to be applied once per environment.

### 4. Open

The deploy script prints the app URL. Sign in with OAuth, then walk Screen 1 (Search) to Screen 2 (Load) to Screen 3 (Analyze).

Prerequisites for the deployed app to return data:

1. The `../automated/` pipeline has produced the three gold tables: `gold_accounts`, `gold_fraud_ring_communities`, `gold_account_similarity_pairs`.
2. The Genie Space referenced by `GRAPH_FRAUD_ANALYST_GENIE_SPACE_ID` points at the AFTER-GDS dataset.
3. The app SP has been granted UC access per step 3 above.

---

## Local development

For UI work, run the apx dev servers:

```bash
apx dev start          # backend + frontend + OpenAPI watcher
apx dev status         # check what's running
apx dev logs -f        # stream logs
apx dev stop           # stop everything
```

The backend reads the same `.env` you created above. Local SQL and Genie calls require `DATABRICKS_HOST` and `DATABRICKS_TOKEN` (or an active `~/.databrickscfg` profile that the SDK can resolve).

### Type checks

```bash
apx dev check          # tsc + ty
```

### Production build

```bash
apx build              # builds .build/ for bundle deploy
```

---

## What's inside

- `src/graph_fraud_analyst/backend/` FastAPI service. Routes in `router.py`, business logic in `services/`, config in `core/_config.py`.
- `src/graph_fraud_analyst/ui/` React + Vite + TanStack Router frontend. Routes in `routes/`, shared state in `lib/flowContext.tsx`, generated OpenAPI client in `lib/api.ts`.
- `scripts/deploy.sh` env-driven bundle deploy with optional log tailing.
- `app.yml` Databricks Apps runtime entrypoint and env wiring.
- `databricks.yml` bundle definition (resources, target, variables).

For deeper detail on the design and the contract between the UI and the backend, see `../demo-client-graph.md` and `../demo-client-graph-v2.md`.
