# fraud-analyst

The Fraud Signal Workbench. A Databricks App built with [apx](https://github.com/databricks-solutions/apx) (FastAPI + React) that surfaces ring-candidate communities, risky accounts, and central hub accounts from the gold tables produced by `../automated/`, then lets an analyst load a subgraph and chat with Genie about it.

## Quick start: deploy to Databricks

The fastest path to a live demo.

### 1. Configure

```bash
cp .env.sample .env
```

Required values:

| Variable | Description |
| --- | --- |
| `DATABRICKS_PROFILE` | Profile name from `~/.databrickscfg`. |
| `FRAUD_ANALYST_WAREHOUSE_ID` | SQL warehouse the FastAPI service uses to query gold tables. |
| `FRAUD_ANALYST_GENIE_SPACE_ID` | Genie Space ID for the AFTER-GDS conversational experience. |
| `FRAUD_ANALYST_CATALOG` | Unity Catalog catalog (default `graph-enriched-lakehouse`). |
| `FRAUD_ANALYST_SCHEMA` | Unity Catalog schema (default `graph-enriched-schema`). |

### 2. Deploy

```bash
./scripts/deploy.sh
```

The script sources `.env`, validates the required IDs, builds the bundle, and runs `databricks bundle deploy` with the right `--var` bindings.

To deploy and stream live app logs in the same shell:

```bash
./scripts/deploy.sh --log
```

That runs the deploy and then tails `databricks apps logs fraud-analyst --follow` until you ctrl-c.

### 3. Open

The deploy command prints the app URL. Sign in with OAuth, then walk Screen 1 (Search) to Screen 2 (Load) to Screen 3 (Analyze).

Prerequisites for the deployed app to return data:

1. The `../automated/` pipeline has produced the three gold tables: `gold_accounts`, `gold_fraud_ring_communities`, `gold_account_similarity_pairs`.
2. The Genie Space referenced by `FRAUD_ANALYST_GENIE_SPACE_ID` points at the AFTER-GDS dataset.

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

- `src/fraud_analyst/backend/` FastAPI service. Routes in `router.py`, business logic in `services/`, config in `core/_config.py`.
- `src/fraud_analyst/ui/` React + Vite + TanStack Router frontend. Routes in `routes/`, shared state in `lib/flowContext.tsx`, generated OpenAPI client in `lib/api.ts`.
- `scripts/deploy.sh` env-driven bundle deploy with optional log tailing.
- `app.yml` Databricks Apps runtime entrypoint and env wiring.
- `databricks.yml` bundle definition (resources, target, variables).

For deeper detail on the design and the contract between the UI and the backend, see `../demo-client-graph.md` and `../demo-client-graph-v2.md`.
