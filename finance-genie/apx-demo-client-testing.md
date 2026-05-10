# Apx Demo Client, Testing Plan

**Companion to:** `demo-client-graph.md` (original proposal), `demo-client-graph-v2.md` (frontend work-item plan F1 through F11), `demo-client-graph-backend.md` (data-pipeline plan), `apx-demo/CLAUDE.md` (apx project conventions).
**Audience:** the agent or engineer running the test pass on the Fraud Signal Workbench frontend at `finance-genie/apx-demo/`.

---

## Why this document exists

The frontend ships in three layers and each layer has its own test surface. This plan tells you what to run, in what order, and what to look at to know it worked.

The three layers, in execution order:

1. **Local**, against the apx dev server with mock services. This is where the bulk of UI verification happens.
2. **Deploy**, to a Databricks Apps target via the workspace bundle.
3. **Deployed**, against the real workspace URL. Smaller checklist but exercises OAuth, resource bindings, and (once the OpenAPI client lands per F11) real Neo4j, Delta, and Genie calls.

Playwright MCP automates the click-paths in layers 1 and 3.

---

## Pre-flight

Before testing anything, all of these should already be true:

- apx CLI installed and on PATH. `apx --version` returns 0.3.x.
- Project is on the latest main with the F1 through F8 commits applied.
- `apx dev check` returns green for both tsc and ty.
- shadcn primitives are installed: button, card, table, checkbox, select, input, badge, dialog, textarea, skeleton, tooltip.
- Light theme in effect by default. IBM Plex fonts load from Google Fonts via `index.html`.
- The three screen routes exist at `routes/_workbench/search.tsx`, `routes/_workbench/load.tsx`, `routes/_workbench/analyze.tsx`.
- The Databricks MCP server is connected to the workspace profile `azure-rk-knight`. Confirm via `manage_workspace(action="status")`.

If any of these is not true, fix that first.

---

## Phase 1, Local testing with mocks

### 1.1 Boot the dev servers

From `finance-genie/apx-demo/`, start the dev environment via the apx MCP `start` tool. This brings up the FastAPI backend, the Vite frontend, and the OpenAPI watcher in one step. The MCP returns the frontend dev URL, which is what you open in the browser.

CLI fallback: `apx dev start`. Then `apx dev status` to confirm all three processes are alive.

If a server fails to boot, fetch the recent log via the apx MCP `logs` tool or `apx dev logs`. Most boot failures trace to a stale port or a missing dependency.

### 1.2 Type and lint baseline

Run `apx dev check` or the MCP `check` tool. Both tsc and ty must report green before doing any UI testing. A red bar here is a hard stop, not a "fix later" item.

### 1.3 Manual walkthrough

Open the dev URL in a regular browser tab. Navigate to `/search` directly because the v1 root still shows the apx welcome page. F10 will replace it with a redirect to `/search` later.

Walk all three screens in order.

**Screen 1 at `/search`**

- Page renders with warm off-white canvas, IBM Plex Sans body, dark grey ink text, sharp 2 to 4 px corners, 1 px borders.
- The "What are you looking for?" card shows three mode cards. Default selected: Fraud rings.
- Switch to Risky accounts. Skeleton rows appear briefly, then a table of accounts with risk bars, velocity pills, merchant-diversity pills, account ages.
- Switch to Central accounts. Hub table renders with neighbors, betweenness bars, shortest paths.
- Switch back to Fraud rings.
- Filters strip: change Date range to Last 7 days, change Minimum amount to 1000, change Max nodes to 200, click Search Neo4j. Skeleton appears, then a fresh result set.
- Open and close the Graph view collapsible at the top of the rings results. Tiles render with stable shapes per ring, deterministic across reloads.
- Click a tile inside Graph view. The corresponding row checkbox in the table below toggles in sync.
- Click a row checkbox directly. The matching tile in Graph view shows the selected ring outline.
- Select two rings. The footer shows "2 rings selected" and the Continue to Load button enables.
- Click Continue to Load.

**Screen 2 at `/load`**

- Header strip shows "Loading 2 rings → Lakehouse" with both ring id pills.
- Pipeline progress card animates 7 steps in sequence at roughly 700 ms each. Each step transitions todo to now (spinning loader) to done (green check).
- Right column populates: Target tables shows 4 fraud_signals tables, Row counts shows live numbers, Quality checks shows 6 entries with green check icons.
- Continue to Analyze stays disabled until the seventh step lands as done. Confirm by clicking it before completion and seeing it ignore the click.
- After completion, click Continue to Analyze.

**Screen 3 at `/analyze`**

- Left sidebar: Schema card lists the four fraud_signals tables as `<details>` elements. Click one open and confirm the column pills render. Try-asking card shows five sample questions.
- Click the first sample question. A question bubble appears on the right of the transcript, then a skeleton bubble, then an answer bubble with the canned text plus a table.
- Click the second sample question. The answer is appended below the first. Confirm the conversation_id is reused across calls (open DevTools, look at the network call payload, the second call sends the same conversation_id the first response returned).
- Type a free-text question into the textarea. Press Enter. The question submits. Press Shift+Enter and confirm a newline inserts without submission.
- Click Export Report. A sonner toast appears with placeholder copy. The modal is F9, not yet built.
- Click Back to Load. Navigation returns to `/load`.
- Click the stepper at the top to jump back to Search. The selection state persists thanks to the FlowProvider; the rings should still be checked.

### 1.4 Browser console and network checks

Open DevTools.

- **Console**: zero errors, zero React warnings, zero CSP warnings. Mock service calls resolve cleanly with no rejected promises.
- **Network**: IBM Plex font loads from Google Fonts. No 404s on icons, static assets, or the apx OpenAPI watcher endpoint.
- **Performance**: Screen 1 first paint under 1 s on localhost. Screen 2 animation runs without dropped frames.

### 1.5 Playwright MCP automation, local

Once the manual walk passes once by hand, automate the same path. Re-running the script on every change catches regressions you would otherwise miss between commits.

The Playwright MCP server is registered in `apx-demo/.mcp.json`. The exact tool names depend on which Playwright MCP server is installed. Common shapes are `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type` or `browser_fill`, `browser_wait_for`, `browser_take_screenshot`, `browser_close`. List the available tools at the start of a run so the script names are accurate.

Recommended script outline for the full three-screen walk:

1. Capture the dev URL via the apx MCP `start` tool. If the server is already running, `apx dev status` reports the URL.
2. Open a new browser session via the Playwright MCP.
3. Navigate to `${devUrl}/search`.
4. Take an accessibility-tree snapshot. Verify the page heading "Surface fraud signals" plus three mode buttons plus the Search Neo4j button are all present by accessible name.
5. Click the Risky accounts mode by accessible name. Wait for the new table by waiting on the text "Velocity" or "Merchant diversity".
6. Click Fraud rings. Wait for the rings table to reappear.
7. Click the first two ring-row checkboxes. Target each by its accessible name "Select RING-0041" and "Select RING-0087" (the labels come from the `aria-label` set in `routes/_workbench/search.tsx`).
8. Click Continue to Load. Wait for the URL to become `/load`.
9. Wait for the seventh pipeline step to land in the done state. The simplest signal is the Continue to Analyze button becoming enabled; wait for it to become enabled, with a 6 s timeout.
10. Click Continue to Analyze. Wait for the URL to become `/analyze`.
11. Click the first sample question. Wait for the answer bubble by waiting for the canned text "Top 10 accounts by risk score across the two loaded rings."
12. Take a screenshot at each screen for the verification artifact. Save to a deterministic path so diffs across runs are easy to inspect.
13. Close the browser session.

Prefer `browser_snapshot` (accessibility tree) over pixel screenshots for assertions. The tree dumps roles and accessible names, which match the v2 plan's component conventions and stay robust under cosmetic changes. Reserve screenshots for one-per-screen verification artifacts.

Pass criteria for Phase 1: every manual checkpoint passes by hand, the Playwright script completes without timeout or assertion miss, console is clean.

---

## Phase 2, Deploy to Databricks

The deploy target is a Databricks App at `https://adb-1098933906466604.4.azuredatabricks.net/` per the project-level `databricks/CLAUDE.md`. Profile: `azure-rk-knight`.

### 2.1 Confirm workspace connection

Use the Databricks MCP `manage_workspace` tool with `action="status"` to confirm the active profile. If the token is expired, refresh via `manage_workspace(action="login", host="https://adb-1098933906466604.4.azuredatabricks.net/")`.

### 2.2 Build the production bundle

From `finance-genie/apx-demo/`, run `apx build`. This produces a static frontend bundle under the project's build output directory and prepares the FastAPI app for production. Confirm the build exits clean. Warnings about missing env vars at build time are acceptable; the values come in at runtime via the resource bindings.

### 2.3 Wire `app.yml` resource bindings

Open `apx-demo/app.yml`. Confirm the `env:` section binds the resources the backend needs at runtime. Per the original proposal at `demo-client-graph.md` lines 656 through 680, the bindings are:

- `DATABRICKS_WAREHOUSE_ID` from the `sql-warehouse` resource keyed `fraud-analyst-warehouse`.
- `GENIE_SPACE_ID` from the `genie-space` resource keyed `fraud-signals-genie`.
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` from the `neo4j-graph-engineering` secret scope keys, matching what `automated/setup_secrets.sh` loads.

If any binding is missing or points at a resource that does not exist in the workspace, add or fix it before deploying. A missing binding turns into a 500 on the corresponding endpoint at runtime, which is harder to debug than a deploy-time error.

### 2.4 Bundle deploy

Run the deploy from `apx-demo/`:

```bash
databricks bundle deploy --profile azure-rk-knight
```

apx may also expose `apx deploy` as a wrapper; check `apx --help` to confirm. The deploy prints the deployed app URL on success. Capture it.

### 2.5 Tail the deployed logs

Use the apx MCP `databricks_apps_logs` tool, or the CLI:

```bash
databricks apps logs fraud-analyst --profile azure-rk-knight
```

Confirm the app boots cleanly. The first signs of life are the FastAPI startup banner and any DI bootstrap logs from `src/fraud_analyst/backend/core/`. If the app crashes on boot, the error is almost always a missing env var or a syntax issue in the production build. Check the build artifact and the resource bindings before assuming a code bug.

Pass criteria for Phase 2: `bundle deploy` exits 0, the deployed app URL is reachable, the logs show a clean startup with zero stack traces.

---

## Phase 3, Test the deployed app

Open the deployed URL in a fresh browser tab. The app uses Databricks OAuth, so the first visit redirects to login. Once authenticated, you land on the apx welcome at `/`, then navigate to `/search` for the workbench.

### 3.1 Manual walkthrough on the deployed app

Repeat the Phase 1 walk against the deployed URL. While the mock services still drive the screens (they ship inside the bundle until F11 swaps them), the deployed walk verifies:

- OAuth flow works end to end with no redirect loops.
- Static assets serve from the FastAPI process. Zero 404s on fonts, icons, or assets.
- IBM Plex loads over HTTPS without mixed-content blocks.
- Theme tokens render the same as on local.
- The build output matches what you saw in dev, no missing CSS or layout regressions.

Once F11 lands and the OpenAPI client takes over, the same walk also exercises real Neo4j, real Delta loads, and a real Genie space. At that point, expand the checklist:

- Screen 1 search latency is acceptable, under 2 s cold and under 500 ms warm.
- Screen 2 row counts match what the gold tables actually contain for the selected rings. Cross-check against `automated/cli/04_validate_gold_tables.py` output.
- Screen 3 Genie answers come from the real Conversation API, including non-canned table results that vary by question.

### 3.2 Playwright MCP automation, deployed

Re-run the Phase 1.5 script against the deployed URL. Two adjustments matter:

- **OAuth handling**: log in once manually in a Playwright session, then save the storage state to a JSON file. On subsequent runs, restore the storage state when creating the browser session so the script skips the login redirect. The Playwright MCP exposes a storage-state argument on its browser-create tool; check the MCP tool list for the exact parameter name.
- **Timeout headroom**: bump every `browser_wait_for` by roughly 50 percent. Network round trips against the workspace are slower than localhost. The seven-step load animation still runs on a 700 ms client-side timer, but everything around it is slower.

Pass criteria for Phase 3: the deployed app reproduces every Phase 1 visual and behavioral check, and the Playwright script completes without timeout.

---

## Playwright MCP, reference notes

The Playwright MCP server lives in `apx-demo/.mcp.json`. To find the exact tool names available right now, list the registered MCP tools at the start of the testing session. The tools in the standard Microsoft Playwright MCP server include:

- **`browser_navigate`**, navigate the active page to a URL. Returns the page snapshot inline so the next step can target by accessible name immediately.
- **`browser_snapshot`**, dump the accessibility tree for the current page. Use this for assertions; the tree shows roles and accessible names, which match the component conventions in the v2 plan.
- **`browser_click`**, click on an element targeted by ref or accessible name.
- **`browser_type`** or **`browser_fill`**, fill an input or textarea.
- **`browser_select_option`**, choose an item from a `<select>`.
- **`browser_press_key`**, press Enter, Shift+Enter, Tab, etc.
- **`browser_wait_for`**, wait for a text or selector to appear or disappear. Prefer this over fixed timeouts; the only place a fixed timeout is appropriate is the seven-step load animation, which needs 4900 to 5500 ms.
- **`browser_take_screenshot`**, save an image. Use one screenshot per screen as a verification artifact.
- **`browser_close`**, end the session.

A few patterns worth standardizing on:

- **Target by accessible name**, not by CSS selector. The v2 plan's component conventions ensure every button has a label and every input has a `<label>` association. Snapshots expose those names directly.
- **Snapshot before assert**, never assert blind. A snapshot is cheap and tells you exactly what the page exposes right now. Assertions over a snapshot are stable across cosmetic changes.
- **Wait on text, not on time**. The exception is the load animation; everywhere else, wait for the answer bubble text, the new heading, or the URL change.
- **One screenshot per screen**, saved to a deterministic path like `tests/playwright/screens/{phase}-{screen}.png`. Diff-friendly across runs.

For a long-running script like the full three-screen walk, set the MCP server's idle timeout to at least 60 s. The default 30 s will time out on the load animation step.

---

## Pass and fail criteria, end to end

Pass:

- `apx dev check` returns green.
- Phase 1 manual walk: every checkpoint passes.
- Phase 1 Playwright script: completes without timeout or assertion miss; per-screen screenshots match the design intent qualitatively.
- Phase 2 deploy: `bundle deploy` exits 0, the app URL is reachable, logs show a clean FastAPI startup with zero stack traces.
- Phase 3 deployed walk: every Phase 1 check reproduces on the deployed app.
- Phase 3 Playwright script: completes against the deployed URL with the bumped timeouts.

Fail conditions to investigate:

- Any console error or React warning in DevTools.
- Any 404 in the Network tab on a font, icon, or static asset.
- Pipeline animation stalls or skips a step.
- Genie answer fails to render its optional table when the canned answer includes one.
- Stepper jump from Screen 3 to Screen 1 loses the selected rings, indicating a FlowProvider regression.
- OAuth login loops or returns to the wrong post-login URL.
- The deploy logs print a stack trace mentioning a missing env var or an unbound resource.

---

## Common issues and troubleshooting

- **Vite HMR fails to update after a route file change**: restart the apx dev server via the MCP `restart` tool. The router-plugin sometimes misses a new route file on first compile and needs a clean restart to regenerate `routeTree.gen.ts`.
- **shadcn component installs into the wrong directory**: `apx components add <name>` writes to `src/<app>/ui/components/ui/`. If a component lands elsewhere, move it manually.
- **Tailwind tokens not resolving**: confirm the `@theme inline` block in `globals.css` is intact and the CSS variable name matches `--color-<name>`. Tailwind v4 reads only that exact prefix.
- **OAuth post-login redirect loops**: clear cookies for the workspace host and retry. Often a stale token from a previous app deploy.
- **Bundle deploy fails with a missing resource**: open `app.yml` and confirm every `valueFrom` resource exists in the workspace under the same `resourceKey`. Use the Databricks MCP `manage_uc_objects` and warehouse listing tools to verify.
- **Playwright script flakes on the load animation**: the 700 ms per step plus a margin gives 5400 ms total for the seven steps. If the wait fires before completion, check whether StrictMode is double-mounting the route in dev. The fetch ref guard in `routes/_workbench/load.tsx` should already handle that, but a regression there will cause the animation to restart and break the wait.

---

## When to update this plan

Re-read and revise this plan when:

- A new screen or major route is added; the manual walkthrough section needs the new steps.
- The mock services are replaced by the real OpenAPI client (work item F11). Phase 1 still exercises the same paths but now hits real services, so latency and pass criteria change.
- A new Databricks resource binding lands in `app.yml`; the Phase 2 section needs the new resource named.
- The Playwright MCP server changes versions; tool names may shift.
- F9's ReportModal lands; Phase 1 Screen 3 needs the modal walkthrough added, and the Playwright script gains an Export step.
