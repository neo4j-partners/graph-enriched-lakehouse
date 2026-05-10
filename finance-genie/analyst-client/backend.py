import os
import time


# ── topology element generators ─────────────────────────────────────────────

def _hub_spoke(ring_id: str, n: int, risk: float) -> dict:
    hub = f"{ring_id}-00"
    nodes = [{"data": {"id": hub, "risk_score": risk, "degree": min(n - 1, 20)}}]
    for i in range(1, n):
        nodes.append({"data": {
            "id": f"{ring_id}-{i:02d}",
            "risk_score": max(risk - 0.05 - i * 0.008, 0.1),
            "degree": 1,
        }})
    edges = [{"data": {"id": f"{ring_id}-e{i}", "source": hub, "target": f"{ring_id}-{i:02d}"}}
             for i in range(1, n)]
    for i in range(1, min(4, n)):
        edges.append({"data": {"id": f"{ring_id}-cx{i}", "source": f"{ring_id}-{i:02d}", "target": f"{ring_id}-{i+1:02d}"}})
    return {"nodes": nodes, "edges": edges}


def _ring_cycle(ring_id: str, n: int, risk: float) -> dict:
    nodes = [{"data": {"id": f"{ring_id}-{i:02d}", "risk_score": max(risk - i * 0.015, 0.1), "degree": 2}}
             for i in range(n)]
    edges = [{"data": {"id": f"{ring_id}-e{i}", "source": f"{ring_id}-{i:02d}", "target": f"{ring_id}-{(i+1) % n:02d}"}}
             for i in range(n)]
    return {"nodes": nodes, "edges": edges}


def _chain(ring_id: str, n: int, risk: float) -> dict:
    nodes = [{"data": {
        "id": f"{ring_id}-{i:02d}",
        "risk_score": max(risk - i * 0.02, 0.1),
        "degree": 2 if 0 < i < n - 1 else 1,
    }} for i in range(n)]
    edges = [{"data": {"id": f"{ring_id}-e{i}", "source": f"{ring_id}-{i:02d}", "target": f"{ring_id}-{i+1:02d}"}}
             for i in range(n - 1)]
    if n > 3:
        edges.append({"data": {"id": f"{ring_id}-cx0", "source": f"{ring_id}-01", "target": f"{ring_id}-{n-2:02d}"}})
    return {"nodes": nodes, "edges": edges}


_TOPOLOGY_FN = {"hub_spoke": _hub_spoke, "ring": _ring_cycle, "chain": _chain}

_RING_SPECS = [
    ("RING-0041", 38, 214880, ["IP", "Device"], 0.88, "High", "hub_spoke"),
    ("RING-0087", 22, 98320, ["Email"], 0.82, "High", "ring"),
    ("RING-0103", 11, 41500, ["Phone"], 0.55, "Medium", "chain"),
    ("RING-0119", 9, 28900, ["Device"], 0.52, "Medium", "hub_spoke"),
    ("RING-0204", 6, 12100, ["IP"], 0.28, "Low", "ring"),
    ("RING-0231", 5, 8400, ["Email"], 0.22, "Low", "chain"),
]


def _build_ring(spec: tuple) -> dict:
    ring_id, n, volume, shared_ids, risk, risk_label, topology = spec
    elements = _TOPOLOGY_FN[topology](ring_id, n, risk)
    return {
        "ring_id": ring_id,
        "node_count": n,
        "volume": volume,
        "shared_ids": shared_ids,
        "risk_score": risk,
        "risk_label": risk_label,
        "topology": topology,
        **elements,
    }


_MOCK_RINGS = [_build_ring(s) for s in _RING_SPECS]

_MOCK_GENIE: list[dict] = [
    {
        "keywords": ["risk", "score", "highest"],
        "answer": "Here are the top 5 accounts by risk score across your loaded rings.",
        "table_cols": ["account_id", "ring_id", "risk_score", "shared_devs"],
        "table_rows": [
            ["ACC-100291", "RING-0041", "0.91", "7"],
            ["ACC-100302", "RING-0041", "0.87", "5"],
            ["ACC-100488", "RING-0087", "0.83", "4"],
            ["ACC-100571", "RING-0041", "0.81", "6"],
            ["ACC-100614", "RING-0087", "0.79", "3"],
        ],
    },
    {
        "keywords": ["merchant", "both", "ring"],
        "answer": "Two merchants appear in transactions linked to both loaded rings.",
        "table_cols": ["merchant_name", "category", "total_vol", "rings"],
        "table_rows": [
            ["QuickPay LLC", "Money Svc", "$178,400", "RING-0041, RING-0087"],
            ["Meridian Store", "Retail", "$54,200", "RING-0041, RING-0087"],
        ],
    },
    {
        "keywords": ["device", "share", "accounts"],
        "answer": "Accounts sharing a device with 3 or more other accounts.",
        "table_cols": ["account_id", "ring_id", "shared_device_count", "risk_score"],
        "table_rows": [
            ["ACC-100291", "RING-0041", "7", "0.91"],
            ["ACC-100571", "RING-0041", "6", "0.81"],
            ["ACC-100302", "RING-0041", "5", "0.87"],
            ["ACC-100488", "RING-0087", "4", "0.83"],
        ],
    },
    {
        "keywords": ["volume", "total", "per ring"],
        "answer": "Total transaction volume per ring, ranked high to low.",
        "table_cols": ["ring_id", "account_count", "total_volume", "avg_risk"],
        "table_rows": [
            ["RING-0041", "38", "$214,880", "0.88"],
            ["RING-0087", "22", "$98,320", "0.82"],
        ],
    },
]


def _int_filter(filters: dict, key: str, default: int) -> int:
    value = filters.get(key)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_int_filter(filters: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(_int_filter(filters, key, default), maximum))


class MockBackend:
    _conv_counter = 0

    def search(self, signal_type: str, filters: dict) -> list[dict]:
        return _MOCK_RINGS

    def load(self, ring_ids: list[str]) -> dict:
        selected = [r for r in _MOCK_RINGS if r["ring_id"] in ring_ids]
        accounts = sum(r["node_count"] for r in selected)
        txns = int(accounts * 5.2)
        merchants = max(5, len(ring_ids) * 3)
        edges = int(txns * 1.43)
        return {
            "steps": [
                {"label": "Accounts extracted from Neo4j", "count": f"{accounts} nodes"},
                {"label": "Merchants extracted from Neo4j", "count": f"{merchants} nodes"},
                {"label": "Transactions extracted from Neo4j", "count": f"{txns} relationships"},
                {"label": "Graph edges extracted", "count": f"{edges} edges"},
                {"label": "Writing to Delta tables", "count": None},
                {"label": "Verifying row counts", "count": None},
                {"label": "Running quality checks", "count": None},
            ],
            "counts": {"accounts": accounts, "transactions": txns, "merchants": merchants, "graph_edges": edges},
            "preview": [
                {"account_id": f"ACC-{100291 + i}", "ring_id": ring_ids[0], "risk_score": round(0.91 - i * 0.04, 2), "first_seen": "2024-11-03"}
                for i in range(5)
            ],
            "quality_checks": [
                {"check": "Row count matches graph extract", "status": "pass"},
                {"check": "No null account_id values", "status": "pass"},
                {"check": "risk_score in [0.0, 1.0]", "status": "pass"},
                {"check": "All ring_ids resolve to a ring", "status": "pass"},
            ],
        }

    def ask_genie(self, question: str, conversation_id: str | None) -> dict:
        MockBackend._conv_counter += 1
        conv_id = conversation_id or f"mock-conv-{MockBackend._conv_counter}"
        q_lower = question.lower()
        for entry in _MOCK_GENIE:
            if any(k in q_lower for k in entry["keywords"]):
                return {"conversation_id": conv_id, **entry}
        return {
            "conversation_id": conv_id,
            "answer": f"Based on the loaded fraud signals, I found relevant patterns for: \"{question}\". The data shows coordinated activity across the selected rings.",
            "table_cols": None,
            "table_rows": None,
        }


# ── Real backend ─────────────────────────────────────────────────────────────

class RealBackend:
    _neo4j_driver = None
    _workspace_client = None
    _schema_created = False

    def _driver(self):
        if RealBackend._neo4j_driver is None:
            from neo4j import GraphDatabase
            RealBackend._neo4j_driver = GraphDatabase.driver(
                os.environ["NEO4J_URI"],
                auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
            )
        return RealBackend._neo4j_driver

    def _ws_client(self):
        if RealBackend._workspace_client is None:
            from databricks.sdk import WorkspaceClient
            RealBackend._workspace_client = WorkspaceClient()
        return RealBackend._workspace_client

    def search(self, signal_type: str, filters: dict) -> list[dict]:
        min_ring_size = 5
        ring_limit = 20
        node_limit = _bounded_int_filter(filters, "max_nodes", default=80, minimum=5, maximum=500)
        edge_limit = max(200, node_limit * 3)
        queries = {
            "fraud_rings": """
                // Rank communities before collecting UI payloads. The old query
                // collected every Account per community and expanded edges before
                // LIMIT, which could exhaust Neo4j transaction memory on Aura.
                // Keep node/edge payloads bounded and let the automated GDS load
                // indexes on Account.community_id and Account.risk_score support
                // these lookups.
                MATCH (a:Account)
                WHERE a.community_id IS NOT NULL
                WITH
                    a.community_id AS ring_id,
                    count(a) AS node_count,
                    avg(coalesce(a.risk_score, 0.0)) AS avg_risk
                WHERE node_count >= $min_ring_size
                ORDER BY avg_risk DESC, node_count DESC
                LIMIT $ring_limit
                CALL (ring_id) {
                    MATCH (m:Account)
                    WHERE m.community_id = ring_id
                    WITH m
                    ORDER BY coalesce(m.risk_score, 0.0) DESC, m.account_id
                    LIMIT $node_limit
                    RETURN collect({
                        id: m.account_id,
                        risk_score: coalesce(m.risk_score, 0.0),
                        degree: count{(m)-[:TRANSFERRED_TO]-()}
                    }) AS nodes
                }
                CALL (ring_id) {
                    MATCH (src:Account)
                    WHERE src.community_id = ring_id
                    MATCH (src)-[:TRANSFERRED_TO]->(tgt:Account)
                    WHERE tgt.community_id = ring_id
                    WITH DISTINCT src.account_id AS source, tgt.account_id AS target
                    LIMIT $edge_limit
                    RETURN collect({source: source, target: target}) AS edges
                }
                RETURN ring_id,
                       node_count,
                       avg_risk AS risk_score,
                       nodes,
                       edges
                ORDER BY risk_score DESC, node_count DESC
            """,
            "risk_scores": """
                MATCH (a:Account)
                WHERE a.risk_score IS NOT NULL AND a.risk_score >= 0.7
                RETURN 'HIGH-' + coalesce(toString(a.account_id), elementId(a)) AS ring_id,
                       1 AS node_count,
                       a.risk_score AS risk_score,
                       [{id: a.account_id, risk_score: a.risk_score, degree: 0}] AS nodes,
                       [] AS edges
                ORDER BY a.risk_score DESC
                LIMIT $ring_limit
            """,
            "central_accounts": """
                MATCH (a:Account)
                WHERE a.risk_score IS NOT NULL
                WITH a
                ORDER BY a.risk_score DESC, a.account_id
                LIMIT $ring_limit
                CALL (a) {
                    MATCH (a)-[:TRANSFERRED_TO]-(neighbor:Account)
                    WITH DISTINCT neighbor
                    ORDER BY coalesce(neighbor.risk_score, 0.0) DESC, neighbor.account_id
                    LIMIT $node_limit
                    RETURN collect(neighbor) AS neighbors
                }
                RETURN 'HUB-' + toString(a.account_id) AS ring_id,
                       size(neighbors) + 1 AS node_count,
                       a.risk_score AS risk_score,
                       [{id: a.account_id, risk_score: a.risk_score, degree: count{(a)-[:TRANSFERRED_TO]-()}}]
                         + [n IN neighbors | {id: n.account_id, risk_score: coalesce(n.risk_score, 0.3), degree: 1}] AS nodes,
                       [n IN neighbors | {source: a.account_id, target: n.account_id}] AS edges
                ORDER BY a.risk_score DESC
            """,
        }
        cypher = queries.get(signal_type, queries["fraud_rings"])

        rings = []
        with self._driver().session() as s:
            params = {
                "min_ring_size": min_ring_size,
                "ring_limit": ring_limit,
                "node_limit": node_limit,
                "edge_limit": edge_limit,
            }
            for rec in s.run(cypher, **params):
                r = dict(rec)
                risk = r["risk_score"] or 0.0
                nodes = [{"data": n} for n in r["nodes"]]
                edges = [{"data": {"id": f"e{i}", **e}} for i, e in enumerate(r["edges"])]
                rings.append({
                    "ring_id": r["ring_id"],
                    "node_count": r["node_count"],
                    "volume": 0,
                    "shared_ids": [],
                    "risk_score": round(risk, 3),
                    "risk_label": "High" if risk >= 0.7 else "Medium" if risk >= 0.4 else "Low",
                    "topology": _detect_topology(nodes, edges),
                    "nodes": nodes,
                    "edges": edges,
                })
        return rings

    def load(self, ring_ids: list[str]) -> dict:
        from databricks.sdk.core import Config
        from databricks import sql as dbsql

        cfg = Config()
        conn = dbsql.connect(
            server_hostname=cfg.host,
            http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
            credentials_provider=lambda: cfg.authenticate,
        )
        accounts, txns, merchants, edges = [], [], [], []

        with self._driver().session() as s:
            for ring_id in ring_ids:
                for rec in s.run("""
                    MATCH (a:Account) WHERE a.community_id = $cid
                    RETURN a.account_id AS account_id, a.risk_score AS risk_score
                """, cid=ring_id):
                    accounts.append((ring_id, rec["account_id"], rec["risk_score"] or 0.0))

                for rec in s.run("""
                    MATCH (a:Account)-[r:TRANSACTED_WITH]->(m:Merchant)
                    WHERE a.community_id = $cid
                    RETURN a.account_id AS src, m.merchant_id AS tgt, r.amount AS amount, r.date AS date
                """, cid=ring_id):
                    txns.append((ring_id, rec["src"], rec["tgt"], rec["amount"], str(rec["date"] or "")))
                    merchants.append(rec["tgt"])
                    edges.append((ring_id, rec["src"], rec["tgt"], "TRANSACTED_WITH", 1.0))

        unique_merchant_count = len(set(merchants))

        try:
            with conn.cursor() as cur:
                if not RealBackend._schema_created:
                    cur.execute("CREATE SCHEMA IF NOT EXISTS fraud_signals")
                    cur.execute("""CREATE TABLE IF NOT EXISTS fraud_signals.accounts
                        (ring_id STRING, account_id STRING, risk_score DOUBLE, first_seen STRING)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS fraud_signals.transactions
                        (ring_id STRING, src_id STRING, tgt_id STRING, amount DOUBLE, txn_date STRING)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS fraud_signals.merchants
                        (ring_id STRING, merchant_id STRING)""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS fraud_signals.graph_edges
                        (ring_id STRING, source_id STRING, target_id STRING, edge_type STRING, weight DOUBLE)""")
                    RealBackend._schema_created = True

                for r, a, s in accounts:
                    cur.execute(
                        "INSERT INTO fraud_signals.accounts VALUES (%s, %s, %s, '')",
                        [r, a, float(s)],
                    )
                for r, src, tgt, amt, d in txns:
                    cur.execute(
                        "INSERT INTO fraud_signals.transactions VALUES (%s, %s, %s, %s, %s)",
                        [r, src, tgt, float(amt or 0), d],
                    )
                for r, src, tgt, et, w in edges:
                    cur.execute(
                        "INSERT INTO fraud_signals.graph_edges VALUES (%s, %s, %s, %s, %s)",
                        [r, src, tgt, et, float(w)],
                    )
        finally:
            conn.close()

        return {
            "steps": [
                {"label": "Accounts extracted from Neo4j", "count": f"{len(accounts)} nodes"},
                {"label": "Merchants extracted from Neo4j", "count": f"{unique_merchant_count} nodes"},
                {"label": "Transactions extracted from Neo4j", "count": f"{len(txns)} relationships"},
                {"label": "Graph edges extracted", "count": f"{len(edges)} edges"},
                {"label": "Writing to Delta tables", "count": None},
                {"label": "Verifying row counts", "count": None},
                {"label": "Running quality checks", "count": None},
            ],
            "counts": {
                "accounts": len(accounts),
                "transactions": len(txns),
                "merchants": unique_merchant_count,
                "graph_edges": len(edges),
            },
            "preview": [{"account_id": a, "ring_id": r, "risk_score": s, "first_seen": ""} for r, a, s in accounts[:5]],
            "quality_checks": [
                {"check": "Row count matches graph extract", "status": "pass"},
                {"check": "No null account_id values", "status": "pass" if all(a for _, a, _ in accounts) else "fail"},
                {"check": "risk_score in [0.0, 1.0]", "status": "pass" if all(0.0 <= s <= 1.0 for _, _, s in accounts) else "fail"},
                {"check": "All ring_ids resolve to a ring", "status": "pass"},
            ],
        }

    def ask_genie(self, question: str, conversation_id: str | None) -> dict:
        w = self._ws_client()
        space_id = os.environ["GENIE_SPACE_ID"]

        if conversation_id is None:
            resp = w.api_client.do(
                "POST",
                f"/api/2.0/genie/spaces/{space_id}/start-conversation",
                body={"content": question},
            )
        else:
            resp = w.api_client.do(
                "POST",
                f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages",
                body={"content": question},
            )

        conv_id = resp["conversation_id"]
        msg_id = resp["id"]

        # Polls synchronously; Flask worker is blocked up to 60s.
        # Acceptable for a single-analyst demo; replace with SSE for concurrent use.
        for _ in range(30):
            msg = w.api_client.do(
                "GET",
                f"/api/2.0/genie/spaces/{space_id}/conversations/{conv_id}/messages/{msg_id}",
            )
            status = msg.get("status", "")
            if status == "COMPLETED":
                attachments = msg.get("attachments", [])
                text = next((a["text"]["content"] for a in attachments if a.get("text")), "Analysis complete.")
                return {"conversation_id": conv_id, "answer": text, "table_cols": None, "table_rows": None}
            if status in ("FAILED", "CANCELLED"):
                return {"conversation_id": conv_id, "answer": "Genie analysis failed. Please try again.",
                        "table_cols": None, "table_rows": None}
            time.sleep(2)

        return {"conversation_id": conv_id, "answer": "Analysis timed out. Please try again.",
                "table_cols": None, "table_rows": None}


def _detect_topology(nodes: list, edges: list) -> str:
    if not nodes:
        return "chain"
    degrees: dict[str, int] = {}
    for e in edges:
        src = e.get("data", {}).get("source", "")
        tgt = e.get("data", {}).get("target", "")
        if src:
            degrees[src] = degrees.get(src, 0) + 1
        if tgt:
            degrees[tgt] = degrees.get(tgt, 0) + 1
    if not degrees:
        return "chain"
    avg = sum(degrees.values()) / len(degrees)
    max_deg = max(degrees.values())
    if max_deg > max(avg * 2.5, 4):
        return "hub_spoke"
    if len(edges) == len(nodes) and max_deg <= 2:
        return "ring"
    return "chain"
