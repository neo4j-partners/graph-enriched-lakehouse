# Fraud Analyst App — Implementation Proposal

**Stack:** Flask 3.0.3 (pre-installed) + static HTML + CDN Cytoscape.js  
**Deploy target:** Databricks Apps  

---

## Decision

Flask serves a single `index.html` from its `static/` directory. Three JSON endpoints handle all backend operations. No build step, no npm, no separate runtime — the wireframe HTML is adapted directly. Cytoscape.js, loaded from CDN, handles both visualization patterns added in the updated design.

---

## File Structure

```
finance-genie/simple-client/
  app.py              # Flask entry + 3 API routes
  backend.py          # Neo4j, Delta, Genie integrations
  app.yaml            # Databricks Apps resource config
  requirements.txt    # neo4j>=5.0  (flask is pre-installed)
  static/
    index.html        # Single page, three-screen wizard
    app.js            # ~150 lines: screen transitions + fetch wiring
    style.css         # Layout and risk color palette
```

---

## Cytoscape.js — Two Rendering Patterns

This is the only non-trivial frontend decision. The updated wireframe has two distinct uses:

### 1. Graph View Grid (Screen 1, results panel)

Six mini Cytoscape canvases in a 2×3 grid, one per ring. Each canvas auto-selects a layout based on the ring's topology:

```js
function pickLayout(elements) {
  const nodes = elements.filter(e => !e.data.source);
  const edges = elements.filter(e => e.data.source);
  const avgDegree = (edges.length * 2) / nodes.length;
  const maxDegree = Math.max(...nodes.map(n =>
    edges.filter(e => e.data.source === n.data.id || e.data.target === n.data.id).length
  ));

  if (maxDegree > avgDegree * 3) return { name: 'cose', idealEdgeLength: 40 };
  if (edges.length === nodes.length) return { name: 'circle' };
  return { name: 'breadthfirst', directed: false };
}
```

Node size encodes hub status; color encodes risk tier:

```js
const riskColor = { high: '#d63031', medium: '#e17055', low: '#00b894' };

cytoscape({
  container: document.getElementById(`ring-${ring.id}`),
  elements: ring.elements,
  style: [
    {
      selector: 'node',
      style: {
        'background-color': ele => riskColor[ele.data('risk')] ?? '#aaa',
        'width': ele => 8 + ele.data('degree') * 3,
        'height': ele => 8 + ele.data('degree') * 3,
      }
    },
    { selector: 'edge', style: { 'width': 1, 'line-color': '#ccc' } }
  ],
  layout: pickLayout(ring.elements),
  userZoomingEnabled: false,
  userPanningEnabled: false,
});
```

Clicking a card selects or deselects the ring (visual border + updates the checkbox in the table below).

### 2. Topology Icons (Results Table, TOPOLOGY column)

Small static thumbnails — 36×36px Cytoscape instances rendered once per row, then frozen:

```js
function renderTopologyIcon(container, elements) {
  const cy = cytoscape({
    container,
    elements,
    style: [
      { selector: 'node', style: { 'width': 6, 'height': 6, 'background-color': '#666' } },
      { selector: 'edge', style: { 'width': 1, 'line-color': '#999' } }
    ],
    layout: pickLayout(elements),
    userZoomingEnabled: false,
    userPanningEnabled: false,
    autoungrabify: true,
  });
  cy.fit();
}
```

### 3. Risk Bar

Pure CSS/HTML — five `<span>` elements, filled count driven by risk score:

```js
function riskBar(score, label) {
  const filled = Math.round(score * 5);
  const color = score > 0.66 ? '#d63031' : score > 0.33 ? '#e17055' : '#00b894';
  const squares = Array.from({ length: 5 }, (_, i) =>
    `<span style="background:${i < filled ? color : '#e0e0e0'};
      width:10px;height:10px;display:inline-block;margin:0 1px;border-radius:1px"></span>`
  ).join('');
  return `<span>${squares}</span> <span>${label}</span>`;
}
```

---

## Flask Routes (`app.py`)

```python
from flask import Flask, jsonify, request, send_from_directory
from backend import search_neo4j, load_to_delta, ask_genie

app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search", methods=["POST"])
def search():
    body = request.get_json()
    signal_type = body["signal_type"]          # "fraud_rings" | "risk_scores" | "central_accounts"
    filters = body.get("filters", {})
    rings = search_neo4j(signal_type, filters)
    return jsonify(rings)


@app.route("/api/load", methods=["POST"])
def load():
    ring_ids = request.get_json()["ring_ids"]
    result = load_to_delta(ring_ids)
    return jsonify(result)


@app.route("/api/genie", methods=["POST"])
def genie():
    body = request.get_json()
    answer = ask_genie(body["question"], body.get("conversation_id"))
    return jsonify(answer)


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", 8000)))
```

---

## Backend Integrations (`backend.py`)

Three functions, each wrapping a different Databricks/Neo4j surface.

### `search_neo4j` — Screen 1

```python
from neo4j import GraphDatabase
import os

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )
    return _driver


CYPHER = {
    "fraud_rings": """
        MATCH (a:Account)-[:TRANSACTED_WITH]->(m:Merchant)
        WHERE a.community_id IS NOT NULL
        WITH a.community_id AS ring_id,
             collect(DISTINCT a) AS accounts,
             collect(DISTINCT m) AS merchants,
             sum(a.risk_score) AS total_risk
        WHERE size(accounts) >= $min_nodes
        RETURN ring_id,
               size(accounts) AS node_count,
               total_risk / size(accounts) AS avg_risk,
               [n IN accounts | {id: n.account_id, risk: n.risk_score, degree: n.degree}] AS nodes,
               [r IN [(a)-[rel:TRANSACTED_WITH]->(m) WHERE a IN accounts | rel]
                | {source: startNode(r).account_id, target: endNode(r).merchant_id}] AS edges
        ORDER BY avg_risk DESC
        LIMIT 20
    """,
}


def search_neo4j(signal_type: str, filters: dict) -> list[dict]:
    query = CYPHER.get(signal_type, CYPHER["fraud_rings"])
    with _get_driver().session() as session:
        result = session.run(query, min_nodes=filters.get("max_nodes", 5))
        return [dict(r) for r in result]
```

### `load_to_delta` — Screen 2

```python
import databricks.sdk as sdk
from databricks.sdk import WorkspaceClient


def load_to_delta(ring_ids: list[str]) -> dict:
    w = WorkspaceClient()
    warehouse_id = os.environ["DATABRICKS_WAREHOUSE_ID"]

    steps = []
    for table, cypher_export in _extract_from_neo4j(ring_ids):
        w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"INSERT INTO fraud_signals.{table} {cypher_export}",
            wait_timeout="30s",
        )
        steps.append({"table": table, "status": "done"})

    counts = {
        row.table_name: row.row_count
        for row in w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement="SELECT table_name, COUNT(*) row_count FROM fraud_signals GROUP BY 1",
            wait_timeout="10s",
        ).result.data_array or []
    }
    return {"steps": steps, "counts": counts}
```

### `ask_genie` — Screen 3

```python
from databricks.sdk.service.dashboards import GenieAPI


def ask_genie(question: str, conversation_id: str | None) -> dict:
    w = WorkspaceClient()
    genie_space_id = os.environ["GENIE_SPACE_ID"]
    genie = GenieAPI(w.api_client)

    if conversation_id is None:
        conv = genie.start_conversation(genie_space_id, question)
    else:
        conv = genie.create_message(genie_space_id, conversation_id, question)

    return {
        "conversation_id": conv.conversation_id,
        "message_id": conv.message_id,
        "answer": conv.attachments[0].text.content if conv.attachments else None,
    }
```

---

## `app.yaml`

```yaml
command: "gunicorn app:app -w 2 -b 0.0.0.0:${DATABRICKS_APP_PORT}"

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

## `requirements.txt`

```
neo4j>=5.0
databricks-sdk>=0.20
gunicorn
```

Flask is pre-installed on Databricks Apps — do not add it.

---

## CDN Imports (in `index.html`)

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.29.2/cytoscape.min.js"></script>
```

No other JS dependencies needed. Chart.js is optional if a risk-score histogram is added later.

---

## Implementation Order

1. `app.py` + static `index.html` shell → confirm Flask serves the page on the app port
2. Screen 1 HTML + `search_neo4j` stub returning mock ring data → confirm graph grid and table render with Cytoscape
3. Wire `/api/search` to real Neo4j → confirm live ring data flows into the graph view
4. Screen 2 HTML + `load_to_delta` → confirm progress display and Delta row counts appear
5. Screen 3 HTML + `ask_genie` → confirm Genie conversation renders in the right pane
6. Export report → `window.print()` or jsPDF (CDN) for PDF download; `/api/save_report` writes a Delta row for Save to Lakehouse

---

## Verification

```bash
# local
DATABRICKS_APP_PORT=8000 NEO4J_URI=... python app.py

# deploy
databricks apps deploy fraud-analyst --source-code-path simple-client/
```

Open the app URL. Walk through: search → select two rings → load → ask a question → export report.
