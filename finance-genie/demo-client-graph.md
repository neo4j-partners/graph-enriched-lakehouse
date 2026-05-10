# Fraud Analyst App, APX Implementation Proposal

**Stack:** FastAPI (Python) + React + TypeScript + Vite + shadcn/ui + Tailwind, scaffolded by APX
**Deploy target:** Databricks Apps (single-app deployment, FastAPI serves the built SPA)
**Companion to:** `simple-client.md` (Flask + CDN alternative), `fraud-analyst.md` (design sketch)

---

## Decision

Build the Fraud Signal Workbench using the **APX** pattern, Databricks' own scaffold for full-stack apps. Python on the backend speaks native to Neo4j, the Databricks SDK, and the Genie Conversation API. React with TypeScript on the frontend gets us a real component system, hot-reload during development, and a typed client generated from the FastAPI OpenAPI spec, so the frontend cannot drift from the backend contract.

The `Fraud Analyst Wireframes.html` design is recreated 1-for-1 in React, using shadcn primitives where they fit and bespoke SVG components for the ring thumbnails and network preview. The wireframe's design tokens (IBM Plex, warm off-white, OKLCH risk palette) translate directly to a Tailwind theme.

Why this pattern over `simple-client.md`:

| Concern | Flask + CDN | APX |
|---|---|---|
| Setup time | Lowest | Medium (one MCP call) |
| Type safety | None on frontend | TypeScript end-to-end, Pydantic on backend |
| Backend/frontend contract | Manual JSON shape agreement | Auto-generated client from OpenAPI |
| Component reuse | Hand-rolled CSS + DOM | shadcn primitives + composable React |
| Dev iteration | Reload page | Vite HMR, basedpyright in watch mode |
| Adding a chart, drawer, or command palette later | Custom JS each time | One `shadcn/get_add_command_for_items` call |
| Deploy artifact | Single Flask process | FastAPI process serving prebuilt static SPA |

The trade is roughly +1 day of scaffolding for a stack that scales to richer interaction (filters with persistent URL state, optimistic UI on the load screen, virtual scrolling on result tables) without rewriting plumbing.

---

## Build Status

> Living section. As files are implemented, items move from `[ ]` to `[x]` and their full code blocks below get replaced with a one-line pointer to the source file.

### Tools available

| Tool | Status | Notes |
|---|---|---|
| `apx` CLI v0.3.8 | ✅ Installed | `/Users/ryanknight/.local/bin/apx`, runs locally |
| apx MCP server | ✅ Registered | `apx-demo/.mcp.json`, exposes `start`, `stop`, `restart`, `routes`, `get_route_info`, `check`, `refresh_openapi`, `add_component`, `search_registry_components`, `list_registry_components`, `logs`, `docs`, `databricks_apps_logs` |
| Playwright MCP server | ✅ Registered | `apx-demo/.mcp.json`, for browser automation during dev |
| Databricks MCP server | ✅ Running | Project root `.mcp.json`, separate from apx |
| `databricks-app-apx` skill | ✅ Installed | `/Users/ryanknight/.claude/skills/databricks-app-apx/`, plus `backend-patterns.md` and `frontend-patterns.md` |
| `databricks-app-python` skill | ✅ Installed | Reference for Databricks app patterns (OAuth, resources, model serving) |
| `databricks-python-sdk` skill | ✅ Installed | Reference for `WorkspaceClient` and SDK methods |

### Scaffold in place

Project lives at `finance-genie/apx-demo/`. App name is `fraud-analyst`, app slug `fraud_analyst`. The proposal below still uses the placeholder `finance_genie` package name in code blocks, all paths should be read as `fraud_analyst` instead until the proposal is updated in place during implementation.

```
apx-demo/
  app.yml                                 # ✅ command: uvicorn fraud_analyst.backend.app:app --workers 2
  databricks.yml                          # ✅ Databricks Apps bundle config
  pyproject.toml                          # ✅ FastAPI, uvicorn, pydantic-settings, databricks-sdk, sqlmodel, psycopg
  package.json + bun.lock                 # ✅ Frontend deps locked
  tsconfig.json                           # ✅
  AGENTS.md, CLAUDE.md, README.md         # ✅ apx-generated docs
  .mcp.json                               # ✅ apx + playwright MCP servers
  src/fraud_analyst/
    __init__.py, _version.pyi, _metadata.pyi    # ✅
    backend/
      app.py                              # ✅ FastAPI entry (apx-generated)
      router.py                           # ✅ Route file (apx-generated, empty)
      models.py                           # ✅ Models file (apx-generated, empty)
      core/                               # ✅ DI, config, lakebase, headers, factory
    ui/
      main.tsx, index.html                # ✅ Vite entry
      routes/__root.tsx, routes/index.tsx # ✅ TanStack Router scaffold
      lib/utils.ts, lib/selector.ts       # ✅
      hooks/use-mobile.ts                 # ✅
      styles/globals.css                  # ✅
      types/vite-env.d.ts                 # ✅
      public/logo.svg                     # ✅
```

### App-specific work, status checklist

Backend (`src/fraud_analyst/backend/`):
- [x] `models.py`, ported the 3-model Pydantic shapes (`RingOut`, `RiskAccountOut`, `HubAccountOut`, `LoadIn`, `LoadOut`, `LoadStep`, `QualityCheck`, `AskIn`, `AskOut`, `AnswerTable`, `GraphNode`, `GraphEdge`, `Graph`)
- [x] `router.py`, defined 5 endpoints: `GET /api/search/rings`, `GET /api/search/risk`, `GET /api/search/hubs`, `POST /api/load`, `POST /api/genie/ask`, each with `response_model` and `operation_id`
- [x] `services/sql.py`, generic warehouse statement-execution helper
- [x] `services/rings.py`, `services/accounts.py`, `services/loader.py` — real reads against `gold_fraud_ring_communities` and `gold_accounts` via Databricks SDK statement execution. The Neo4j-direct path was dropped in favor of the gold tables since W1/W3/W4 columns now exist.
- [x] `services/genie.py`, real Genie Conversation API (`ws.genie.start_conversation_and_wait` / `create_message_and_wait`, attachment query result lookup)
- [x] `core/_config.py` extended with `warehouse_id`, `genie_space_id`, `catalog`, `schema_` fields (env prefix `FRAUD_ANALYST_`)

Frontend (`src/fraud_analyst/ui/`):
- [x] Tailwind theme tokens, ported into `styles/globals.css` (Tailwind v4 `@theme inline` block) so design tokens match the wireframe (F1)
- [x] IBM Plex font links in `index.html` (F1)
- [x] Add shadcn primitives via `add_component`: `button`, `card`, `table`, `checkbox`, `select`, `input`, `badge`, `dialog`, `textarea`, `skeleton`, `tooltip` (F2; pre-existing plus added: table, checkbox, select, dialog, textarea)
- [x] `lib/riskColors.ts`, `lib/ringLayout.ts`, deterministic seed-based layout port of `app.jsx` (F3)
- [x] `components/RingThumb.tsx`, SVG thumbnail (F4)
- [x] `components/NetworkPreview.tsx`, SVG cluster grid (F4)
- [x] `components/Pill.tsx`, `RiskBar.tsx`, `Stepper.tsx`, `Shell.tsx` (F5)
- [x] `routes/_workbench.tsx` layout with `Shell` + `Stepper` + `FlowProvider`, plus `lib/flowContext.tsx` for shared state (selectedRings, conversationId, transcript)
- [x] `routes/_workbench/search.tsx` (Screen 1, F6), `routes/_workbench/load.tsx` (Screen 2, F7), `routes/_workbench/analyze.tsx` (Screen 3, F8)
- [x] `components/ReportModal.tsx` (F9) — shadcn Dialog with summary, loaded rings, conversation log; Print to PDF button; "Save to lakehouse" disabled with tooltip pending backend endpoint
- [x] `routes/index.tsx` redirects to `/search` (F10)
- [x] OpenAPI client at `ui/lib/api.ts` regenerated; screens swapped from mock services to `useSearchRingsSuspense`, `useSearchRiskAccountsSuspense`, `useSearchCentralAccountsSuspense`, `useLoadRings`, `useAskGenie` (F11)
- [x] Mock files (`mockSignals.ts`, `mockLoader.ts`, `mockGenie.ts`) deleted; static reference content moved to `lib/genieReference.ts`

Operational:
- [x] `app.yml`, env bindings added for `FRAUD_ANALYST_WAREHOUSE_ID` (resource `warehouse`), `FRAUD_ANALYST_GENIE_SPACE_ID` (resource `genie`), `FRAUD_ANALYST_CATALOG`, `FRAUD_ANALYST_SCHEMA`
- [x] `databricks.yml`, added `warehouse_id` and `genie_space_id` bundle variables plus matching `sql_warehouse` and `genie_space` resources on the app
- [x] First `apx dev check`, baseline type-check pass (tsc and ty both green)
- [ ] First `apx dev start`, verify both servers come up clean against a workspace where `FRAUD_ANALYST_*` env vars are set (deploy-time check, not local)
- [ ] First end-to-end smoke walk through Screens 1 to 3 against deployed app
- [ ] Bundle deploy via `databricks bundle deploy --profile <your-databricks-profile> --var "warehouse_id=…" --var "genie_space_id=…"`

### Next steps, in order

All implementation steps are complete. The remaining work is a one-shot deploy plus smoke verification:

1. Confirm the Databricks workspace is reachable: `manage_workspace(action="status")` via the Databricks MCP, profile `<your-databricks-profile>`.
2. Get the workspace warehouse ID and Genie Space ID:
   - `databricks warehouses list --profile <your-databricks-profile>`
   - `databricks api get /api/2.0/genie/spaces --profile <your-databricks-profile>`
3. Confirm the gold tables exist and have rows in `graph_enriched_lakehouse.graph_enriched_schema.gold_accounts` and `gold_fraud_ring_communities`. If not, run the `automated/` pipeline first.
4. From `apx-demo/`, run the deploy:
   ```
   databricks bundle deploy --profile <your-databricks-profile> \
     --var "warehouse_id=<id from step 2>" \
     --var "genie_space_id=<id from step 2>"
   ```
5. Open the deployed app URL. Authenticate via OAuth.
6. Walk Screens 1 → 2 → 3 against real data. Reference: `apx-demo-client-testing.md` Phase 3 manual walkthrough section.
7. If anything 500s, tail logs: `databricks apps logs fraud-analyst --profile <your-databricks-profile>`. Most failures trace to a missing column on a gold table or an OAuth scope issue on the Genie call.

---

## File Structure

APX scaffolds this layout. Folders marked `*` are where the wireframe gets implemented.

```
finance-genie/demo-client-graph/
  app.yaml                                    # Databricks Apps resource config
  pyproject.toml                              # Backend deps (FastAPI, neo4j, databricks-sdk)
  src/
    finance_genie/
      backend/
        main.py                               # FastAPI app + static mount
        router.py                       *     # /api/* routes
        models.py                       *     # Pydantic 3-model pattern
        services/
          neo4j_signals.py              *     # search_neo4j logic
          delta_loader.py               *     # load_to_delta logic
          genie_client.py               *     # ask_genie logic
        config.py                             # Env var loading
      frontend/
        package.json
        vite.config.ts
        tailwind.config.ts              *     # Design tokens from wireframe
        index.html
        src/
          main.tsx
          App.tsx                       *     # Stepper shell + routing
          api/
            client.ts                         # Generated from OpenAPI
          components/
            Stepper.tsx                 *
            RingThumb.tsx               *     # SVG, port of app.jsx ringLayout
            NetworkPreview.tsx          *     # SVG grid of clusters
            RiskBar.tsx                 *
            Pill.tsx                    *
            ui/                               # shadcn primitives (button, card, table…)
          screens/
            Screen1Search.tsx           *
            Screen2Load.tsx             *
            Screen3Analyze.tsx          *
            ReportModal.tsx             *
          lib/
            ringLayout.ts               *     # Deterministic seed-based layout
            riskColors.ts               *
```

---

## Design System Translation

The wireframe's CSS variables become Tailwind theme tokens, so the React components style themselves with `bg-canvas`, `text-ink`, `border-line` instead of inline hex codes. This is the part most worth keeping faithful to the wireframe, since the analyst-tool aesthetic depends on it.

`tailwind.config.ts`:

```ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas:    '#fafaf9',
        'canvas-soft': '#f3f3f0',
        surface:   '#ffffff',
        ink:       '#171717',
        'ink-2':   '#404040',
        muted:     '#737373',
        line:      '#e6e5e0',
        'line-2':  '#d4d3cd',
        'line-3':  '#c2c1ba',
        accent:    '#3a4756',
        'accent-2': '#1f2937',
        'accent-soft': '#eef0f3',
        risk: {
          high: 'oklch(60% 0.12 25)',
          med:  'oklch(72% 0.12 80)',
          low:  'oklch(62% 0.08 145)',
        },
        good:    'oklch(55% 0.10 150)',
        pending: '#8a8a85',
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '3px',
        lg: '4px',
      },
      fontSize: {
        base: ['14px', '1.5'],
      },
    },
  },
} satisfies Config;
```

IBM Plex loads through `index.html` `<link>` tags. The `font-variant-numeric: tabular-nums` rule used throughout the wireframe's tables maps to Tailwind's `tabular-nums` utility.

---

## Backend, Pydantic Models (`models.py`)

Following the APX 3-model pattern (`EntityIn`, `EntityRecord`, `EntityOut`). Inputs validate what the client sends, records hold the internal shape, and outs control the response wire format.

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Search ──────────────────────────────────────────────────────────────
SignalType = Literal['fraud_rings', 'risk_scores', 'central_accounts']


class SearchIn(BaseModel):
    signal_type: SignalType
    date_range: str = 'Last 30 days'
    min_amount: int = Field(default=500, ge=0)
    max_nodes: int = Field(default=500, ge=1, le=5000)


class GraphNode(BaseModel):
    id: str
    risk: Literal['H', 'M', 'L']
    is_hub: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str


class RingRecord(BaseModel):
    ring_id: str
    nodes: int
    volume: int
    shared_identifiers: list[str]
    risk: Literal['H', 'M', 'L']
    risk_score: float
    topology: Literal['star', 'mesh', 'chain']
    graph: dict[str, list]   # {"nodes": [...], "edges": [...]} for thumbnail render


class RingOut(RingRecord):
    pass


class RiskAccountOut(BaseModel):
    account_id: str
    risk_score: float
    velocity: Literal['Low', 'Medium', 'High']
    merchant_diversity: Literal['Low', 'Medium', 'High']
    account_age_days: int


class HubAccountOut(BaseModel):
    account_id: str
    betweenness: float
    shortest_paths: int
    neighbors: int


# ── Load ────────────────────────────────────────────────────────────────
class LoadIn(BaseModel):
    ring_ids: list[str]


class LoadStep(BaseModel):
    label: str
    status: Literal['done', 'now', 'todo']
    detail: str | None = None


class QualityCheck(BaseModel):
    name: str
    passed: bool


class LoadOut(BaseModel):
    target_tables: list[str]
    steps: list[LoadStep]
    row_counts: dict[str, int]
    quality_checks: list[QualityCheck]


# ── Genie ───────────────────────────────────────────────────────────────
class AskIn(BaseModel):
    question: str
    conversation_id: str | None = None


class AnswerTable(BaseModel):
    headers: list[str]
    rows: list[list[str]]


class AskOut(BaseModel):
    conversation_id: str
    message_id: str
    text: str
    table: AnswerTable | None = None
    summary: str | None = None
```

---

## Backend, Routes (`router.py`)

`response_model` on every route is the rule that makes the OpenAPI client work, the frontend gets typed methods for free.

```python
from fastapi import APIRouter, HTTPException
from .models import (
    SearchIn, RingOut, RiskAccountOut, HubAccountOut,
    LoadIn, LoadOut,
    AskIn, AskOut,
)
from .services import neo4j_signals, delta_loader, genie_client

router = APIRouter(prefix='/api', tags=['fraud-signals'])


@router.post('/search/rings', response_model=list[RingOut])
async def search_rings(body: SearchIn):
    return neo4j_signals.search_rings(body)


@router.post('/search/risk', response_model=list[RiskAccountOut])
async def search_risk(body: SearchIn):
    return neo4j_signals.search_risk_accounts(body)


@router.post('/search/hubs', response_model=list[HubAccountOut])
async def search_hubs(body: SearchIn):
    return neo4j_signals.search_central_accounts(body)


@router.post('/load', response_model=LoadOut)
async def load_to_lakehouse(body: LoadIn):
    if not body.ring_ids:
        raise HTTPException(status_code=400, detail='ring_ids cannot be empty')
    return delta_loader.load_rings(body.ring_ids)


@router.post('/genie/ask', response_model=AskOut)
async def ask(body: AskIn):
    return genie_client.ask(body.question, body.conversation_id)
```

---

## Backend, FastAPI Entry (`main.py`)

```python
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .router import router as api_router

app = FastAPI(title='Fraud Signal Workbench', version='0.1.0')
app.include_router(api_router)

# Serve the built React SPA
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / 'frontend' / 'dist'
if FRONTEND_DIST.exists():
    app.mount('/', StaticFiles(directory=FRONTEND_DIST, html=True), name='spa')


if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('DATABRICKS_APP_PORT', 8000))
    uvicorn.run('finance_genie.backend.main:app', host='0.0.0.0', port=port)
```

---

## Backend Services (Sketches)

The three service modules wrap the same surfaces as `simple-client.md`'s `backend.py`. Functions return Pydantic models directly so FastAPI's `response_model` path stays cheap.

### `neo4j_signals.py`

```python
from neo4j import GraphDatabase
from ..config import settings
from ..models import SearchIn, RingRecord, RingOut

CYPHER_RINGS = """
MATCH (a:Account)-[:TRANSACTED_WITH]->(m:Merchant)
WHERE a.community_id IS NOT NULL AND a.last_seen >= $since
WITH a.community_id AS ring_id,
     collect(DISTINCT a) AS accounts,
     collect(DISTINCT m) AS merchants,
     sum(a.risk_score) AS total_risk
WHERE size(accounts) >= 5 AND size(accounts) <= $max_nodes
RETURN ring_id,
       size(accounts) AS node_count,
       sum([acc IN accounts | acc.last_volume])[0] AS volume,
       total_risk / size(accounts) AS avg_risk,
       [n IN accounts | {id: n.account_id, risk: n.risk_tier, is_hub: n.is_hub}] AS nodes,
       [r IN [(a)-[rel:TRANSACTED_WITH]->(m) WHERE a IN accounts | rel]
        | {source: startNode(r).account_id, target: endNode(r).merchant_id}] AS edges
ORDER BY avg_risk DESC
LIMIT 20
"""

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )
    return _driver


def search_rings(body: SearchIn) -> list[RingOut]:
    with _get_driver().session() as session:
        result = session.run(CYPHER_RINGS, max_nodes=body.max_nodes, since=_date_floor(body.date_range))
        return [_record_to_ring(r) for r in result]
```

### `delta_loader.py`

Uses the Databricks SDK statement execution API to write extracted subgraphs into `fraud_signals.*` Delta tables. Returns a `LoadOut` whose `steps` array drives the wireframe's progress list animation on Screen 2.

### `genie_client.py`

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieAPI
from ..config import settings
from ..models import AskOut, AnswerTable


def ask(question: str, conversation_id: str | None) -> AskOut:
    w = WorkspaceClient()
    genie = GenieAPI(w.api_client)

    if conversation_id is None:
        conv = genie.start_conversation_and_wait(settings.genie_space_id, question)
    else:
        conv = genie.create_message_and_wait(settings.genie_space_id, conversation_id, question)

    attachment = conv.attachments[0] if conv.attachments else None
    table = None
    if attachment and attachment.query and attachment.query.statement_id:
        result = w.statement_execution.get_statement(attachment.query.statement_id)
        if result.result and result.result.data_array:
            table = AnswerTable(
                headers=[c.name for c in result.manifest.schema.columns],
                rows=[[str(v) for v in row] for row in result.result.data_array],
            )

    return AskOut(
        conversation_id=conv.conversation_id,
        message_id=conv.message_id,
        text=(attachment.text.content if attachment and attachment.text else ''),
        table=table,
        summary=None,
    )
```

---

## Frontend Implementation

### Generated API client

After the backend defines `response_model` on every route, the OpenAPI spec is fetched and converted to a typed client:

```bash
# Run during dev when the backend changes
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi.json \
  --output src/api \
  --client fetch
```

Now the frontend calls `await FraudSignalsService.searchRings({ requestBody: { signal_type: 'fraud_rings', ... } })` and gets a typed `RingOut[]`.

### shadcn primitives to add

One MCP call up front:

```bash
mcp-cli call shadcn/get_add_command_for_items '{
  "items": [
    "@shadcn/button",
    "@shadcn/card",
    "@shadcn/table",
    "@shadcn/checkbox",
    "@shadcn/select",
    "@shadcn/input",
    "@shadcn/badge",
    "@shadcn/dialog",
    "@shadcn/textarea",
    "@shadcn/skeleton",
    "@shadcn/tooltip"
  ]
}'
```

These cover every interactive surface in the wireframe. The radio-card "What are you looking for?" choices stay custom since they are visually distinctive enough to be worth a bespoke component.

### `RingThumb.tsx`, port of `app.jsx`

The wireframe's `ringLayout` and `RingThumb` translate to TypeScript with no functional changes, just types added. The deterministic seed (`ringSeed`) keeps every render stable.

```tsx
import { useMemo } from 'react';

type Risk = 'H' | 'M' | 'L';
type Topology = 'star' | 'mesh' | 'chain';

export interface Ring {
  id: string;
  nodes: number;
  topology: Topology;
  risk: Risk;
}

const RISK_VAR: Record<Risk, string> = {
  H: 'var(--tw-color-risk-high, oklch(60% 0.12 25))',
  M: 'var(--tw-color-risk-med,  oklch(72% 0.12 80))',
  L: 'var(--tw-color-risk-low,  oklch(62% 0.08 145))',
};

export function ringSeed(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return () => {
    h = (h * 9301 + 49297) % 233280;
    return h / 233280;
  };
}

// ringLayout(...) port omitted for brevity, identical to app.jsx

export function RingThumb({ ring, w = 96, h = 44, selected }: {
  ring: Ring; w?: number; h?: number; selected?: boolean;
}) {
  const { nodes, edges } = useMemo(
    () => ringLayout(ring, w, h, { maxNodes: 12 }),
    [ring.id, w, h]
  );
  const stroke = RISK_VAR[ring.risk];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden>
      <g stroke={selected ? stroke : 'var(--tw-color-line-3)'} strokeWidth={0.7} fill="none" opacity={0.85}>
        {edges
          .filter(([a, b]) => nodes[a] && nodes[b])
          .map(([a, b], i) => (
            <line key={i} x1={nodes[a].x} y1={nodes[a].y} x2={nodes[b].x} y2={nodes[b].y} />
          ))}
      </g>
      <g>
        {nodes.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={p.hub ? 2.6 : 1.8}
            fill={selected || p.hub ? stroke : 'var(--tw-color-ink-2)'}
            opacity={p.hub ? 1 : 0.85}
          />
        ))}
      </g>
    </svg>
  );
}
```

`NetworkPreview.tsx` is a structural copy of the wireframe's `NetworkPreview` component, with `onToggle` typed to `(id: string) => void` and the parent passing in selected state from a typed React Context, not prop-drilled state.

### Screens

Each screen becomes a single TSX file matching the wireframe section by section.

`Screen1Search.tsx` composes:
1. The "What are you looking for?" card with three custom choice cards
2. The Filters strip using shadcn `<Select>` and `<Input>`
3. Either an empty-state SVG, or `<RingResults>` / `<RiskResults>` / `<HubResults>` depending on `mode`
4. `<RingResults>` renders `<NetworkPreview>` (collapsible) + the data table with `<RingThumb>` per row

`Screen2Load.tsx` drives the progress animation client-side after `POST /api/load` returns. The backend returns the full `LoadOut` immediately. The frontend animates through `steps` on a 700ms timer to match the wireframe rhythm. This decouples the visual choreography from the actual server timing, which can be sub-second.

`Screen3Analyze.tsx` wires `<Sidebar>` with `<details>`-driven schema cards and sample-question buttons to a transcript pane. Pressing Enter or clicking "Ask" calls `POST /api/genie/ask` and appends the result. The Export Report button opens `<ReportModal>` (shadcn `<Dialog>` + report sections from the wireframe).

### App shell and routing

The wireframe's stepper drives a 3-step linear flow. URL state ties it together:

```tsx
// App.tsx
import { useState } from 'react';
import { Shell } from './components/Shell';
import { Screen1Search } from './screens/Screen1Search';
import { Screen2Load } from './screens/Screen2Load';
import { Screen3Analyze } from './screens/Screen3Analyze';

export default function App() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedRings, setSelectedRings] = useState<string[]>([]);

  return (
    <Shell step={step} onJump={setStep} user="J. Lin · Financial Crimes">
      {step === 1 && (
        <Screen1Search
          selectedRings={selectedRings}
          onToggleRing={id => setSelectedRings(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])}
          onNext={() => setStep(2)}
        />
      )}
      {step === 2 && <Screen2Load selectedRings={selectedRings} onBack={() => setStep(1)} onNext={() => setStep(3)} />}
      {step === 3 && <Screen3Analyze selectedRings={selectedRings} onBack={() => setStep(2)} />}
    </Shell>
  );
}
```

If deep linking matters later, swap `useState` for `useSearchParams` from React Router. Skip it for v1.

---

## `app.yaml`

The Databricks Apps resource bindings stay close to `simple-client.md`. The command runs uvicorn against the FastAPI app, which serves both `/api/*` and the prebuilt SPA from `frontend/dist`.

```yaml
command: "uvicorn finance_genie.backend.main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT}"

env:
  - name: DATABRICKS_WAREHOUSE_ID
    valueFrom:
      resourceType: sql-warehouse
      resourceKey: fraud-analyst-warehouse
  - name: GENIE_SPACE_ID
    valueFrom:
      resourceType: genie-space
      resourceKey: fraud-signals-genie
  - name: NEO4J_URI
    valueFrom:
      resourceType: secret
      resourceKey: neo4j-uri
  - name: NEO4J_USER
    valueFrom:
      resourceType: secret
      resourceKey: neo4j-user
  - name: NEO4J_PASSWORD
    valueFrom:
      resourceType: secret
      resourceKey: neo4j-password
```

---

## `pyproject.toml`

```toml
[project]
name = "finance-genie"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "neo4j>=5.0",
  "databricks-sdk>=0.40",
  "pydantic>=2.9",
  "pydantic-settings>=2.5",
]

[tool.basedpyright]
typeCheckingMode = "standard"
```

---

## APX Workflow

```bash
# Phase 1, Initialize (one time)
mcp-cli call apx/start '{}'
mcp-cli call apx/status '{}'

# Phase 2, Backend, write models.py + router.py + services/

# Phase 3, Frontend, add shadcn pieces and screens
mcp-cli call shadcn/get_add_command_for_items '{ "items": ["@shadcn/button", ... ] }'

# Phase 4, Test
mcp-cli call apx/dev_check '{}'                 # basedpyright + tsc + eslint
curl http://localhost:8000/openapi.json | jq '.paths | keys'
curl -X POST http://localhost:8000/api/search/rings \
  -H 'content-type: application/json' \
  -d '{"signal_type":"fraud_rings","date_range":"Last 30 days","min_amount":500,"max_nodes":500}' | jq .
mcp-cli call apx/get_frontend_url '{}'

# Phase 5, Deploy
mcp-cli call apx/deploy '{}'
databricks apps logs fraud-analyst --profile <your-databricks-profile>
```

---

## Implementation Order

1. `apx/start` and confirm Vite + FastAPI both come up via `apx/status`.
2. Drop in the IBM Plex font links and `tailwind.config.ts` tokens. Verify the canvas color and IBM Plex render in a stub page.
3. Implement `models.py` and route stubs that return mock data shaped exactly like the wireframe's `RINGS`, `RISK_ACCOUNTS`, `HUB_ACCOUNTS`, `TABLES`, `ANSWERS`. Confirm OpenAPI client generation produces clean types.
4. Build `<Shell>`, `<Stepper>`, and the empty Screen 1 state. This unlocks visual review of the design tokens applied across surfaces.
5. Port `RingThumb` and `NetworkPreview` as pure SVG components. Render Screen 1 with the mock ring list against real API stubs.
6. Wire `neo4j_signals.search_rings` to a live Neo4j instance, retire the mock.
7. Build Screen 2 with the animated progress list. Wire `delta_loader.load_rings` to real Databricks SDK statement execution.
8. Build Screen 3, the Genie Q&A pane, then the `<ReportModal>`.
9. Print-to-PDF or jsPDF for download. `POST /api/reports` writes a Delta row for the "Save to lakehouse" action.
10. `apx/deploy` and walk the full flow on the deployed app.

---

## Verification

```bash
# Local dev (APX manages this; this is the equivalent if running by hand)
DATABRICKS_APP_PORT=8000 uv run uvicorn finance_genie.backend.main:app --reload &
cd src/finance_genie/frontend && npm run dev

# Type checks
mcp-cli call apx/dev_check '{}'

# End-to-end smoke test
# 1. Open the frontend URL
# 2. Pick "Fraud rings", click Search Neo4j
# 3. Select RING-0041 and RING-0087, click Load
# 4. Watch progress, click Continue
# 5. Click a sample question, get a Genie answer with table
# 6. Click Export Report, verify PDF or Save to lakehouse
```

---

## Background Research and References

The proposal draws from the following sources, listed by category for follow-up reading.

### Design source (handed off via Anthropic Design Bundle)

- `fraud-analyst/README.md`, the bundle's instructions to coding agents. Key rule: recreate the visual output, not the prototype's internal HTML structure.
- `fraud-analyst/project/Fraud Analyst Wireframes.html`, the inline `<style>` block contains the canonical design tokens (warm off-white `#fafaf9` canvas, IBM Plex pairing, OKLCH risk palette, 1px borders, 3 to 4px corner radii).
- `fraud-analyst/project/app.jsx`, the prototype React code. Loaded via Babel-standalone in the wireframe. Production code in this proposal compiles ahead of time through Vite, but the component structure, the `ringLayout` deterministic seed, and the canned Genie answer shapes are taken directly from this file.
- `fraud-analyst/chats/chat1.md`, the design conversation. Confirms the design intent: "clean light aesthetic, wireframe feel, easy to translate to code", and the explicit choice of "row thumbnails plus collapsible network view" as the Screen 1 graph visualization.

### APX framework

- The `databricks-app-apx` skill ground truth (`/Users/ryanknight/projects/databricks/ai-dev-kit/.test/skills/databricks-app-apx/ground_truth.yaml`). Authoritative for the file structure, the 3-model Pydantic pattern, the `response_model` requirement on every FastAPI route, and the `apx/start`, `apx/dev_check`, `apx/deploy` MCP tool surface. Also documents `apx/get_frontend_url` and the `databricks apps logs` integration.
- `simple-client.md`, the parallel Flask proposal. Useful as a delta: this APX proposal swaps `simple-client/`'s Flask + static HTML for FastAPI + React, but the three backend integrations (Neo4j, Delta, Genie) and the `app.yaml` resource bindings are identical.
- `fraud-analyst.md`, the original design sketch. Establishes the analyst persona, the three-step workflow, and the workflow rationale (Neo4j for structural patterns, Delta for aggregation and governance).

### Frontend stack references

- shadcn/ui, https://ui.shadcn.com. Component primitives generated into the project source rather than installed as a dependency, fits the APX scaffold's frontend conventions.
- Tailwind CSS, https://tailwindcss.com/docs. Theme extension via `tailwind.config.ts` is how the wireframe's CSS variables become utility classes.
- Vite, https://vitejs.dev. Hot-module reload during development, ahead-of-time build for the static SPA served by FastAPI in production.
- React 18, https://react.dev.
- IBM Plex font family, https://www.ibm.com/plex. Available through Google Fonts; the wireframe loads `IBM Plex Sans` weights 400/500/600 and `IBM Plex Mono` weights 400/500.

### Backend stack references

- FastAPI, https://fastapi.tiangolo.com. The `response_model` parameter on path operations is what powers the OpenAPI schema generation that the typed frontend client consumes.
- Pydantic v2, https://docs.pydantic.dev/latest/. The 3-model `In`/`Record`/`Out` separation is a Pydantic idiom, not a FastAPI one.
- Databricks Python SDK, https://databricks-sdk-py.readthedocs.io. Used for statement execution against SQL warehouses (`w.statement_execution`) and Genie Conversation API (`GenieAPI(w.api_client)`).
- Neo4j Python Driver, https://neo4j.com/docs/python-manual/current/. Standard `GraphDatabase.driver` with session-per-request usage.
- OpenAPI TypeScript codegen, https://github.com/ferdikoomen/openapi-typescript-codegen. Generates the `src/api/` client from the FastAPI `/openapi.json`.

### Operational references

- Databricks Apps resource bindings (`app.yaml` `valueFrom` syntax for `sql-warehouse`, `genie-space`, and `secret` resources). Same convention as `simple-client.md`.
- `databricks apps logs <app-name> --profile <profile>` for inspecting deployed app stdout/stderr. The APX MCP server can also fetch these logs on request.

### Decisions that did not make this proposal, and why

- **Cytoscape.js**, used in `simple-client.md`. Skipped here because the wireframe's pure-SVG ring thumbnails and network preview do everything we need without a 200KB layout engine. Deterministic seed-based layouts render identically each time and are trivial to test.
- **Next.js**, despite being mentioned alongside React in the user request. Vite + React is enough for a single-bundle SPA. Next.js' SSR, file-based routing, and edge functions add no value when the FastAPI backend already owns the API surface and Databricks Apps does not benefit from a Node runtime. Revisit if SEO or per-route data loading ever becomes a goal, neither applies to an internal compliance tool.
- **WebSockets for Screen 2 progress**, considered for live ingestion updates. Rejected for v1 because the wireframe shows a fixed 7-step animation. The backend can return the full `LoadOut` and let the client choreograph the timing. Add SSE or WebSockets later if real ingestion takes long enough that real-time feedback adds value.
