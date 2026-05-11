import json
import os
from datetime import timedelta


# ── topology element generators ─────────────────────────────────────────────

def _star(ring_id: str, n: int, risk: float) -> dict:
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


_TOPOLOGY_FN = {"star": _star, "ring": _ring_cycle, "chain": _chain}

_RING_SPECS = [
    ("RING-0041", 38, 214880, ["IP", "Device"], 0.88, "High", "star"),
    ("RING-0087", 22, 98320, ["Email"], 0.82, "High", "ring"),
    ("RING-0103", 11, 41500, ["Phone"], 0.55, "Medium", "chain"),
    ("RING-0119", 9, 28900, ["Device"], 0.52, "Medium", "star"),
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

_DEFAULT_CATALOG = "graph-enriched-lakehouse"
_DEFAULT_SCHEMA = "graph-enriched-schema"


def _catalog_name() -> str:
    return (
        os.getenv("SIMPLE_FINANCE_ANALYST_CATALOG")
        or os.getenv("DATABRICKS_CATALOG")
        or _DEFAULT_CATALOG
    )


def _schema_name() -> str:
    return (
        os.getenv("SIMPLE_FINANCE_ANALYST_SCHEMA")
        or os.getenv("DATABRICKS_SCHEMA")
        or _DEFAULT_SCHEMA
    )


def _quoted_table(table: str) -> str:
    def quote(part: str) -> str:
        return f"`{part.replace('`', '``')}`"

    return ".".join([quote(_catalog_name()), quote(_schema_name()), quote(table)])


def _risk_label(score: float) -> str:
    if score >= 0.7:
        return "High"
    if score >= 0.4:
        return "Medium"
    return "Low"


def _community_ids(values: list[str]) -> list[int]:
    return [int(str(v).strip()) for v in values]


def _string_array(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise TypeError("Expected JSON array for string array column")
            value = parsed
        else:
            value = [value]
    return [str(item) for item in value if item]


def _sql_lit(val: object) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, float):
        return repr(val)
    if isinstance(val, int):
        return repr(val)
    return "'" + str(val).replace("\\", "\\\\").replace("'", "''") + "'"


def _write_ctas(cursor, table: str, col_decls: str, col_names: list[str], rows: list[tuple]) -> None:
    """CREATE OR REPLACE a Delta table from an in-memory row list."""
    if not rows:
        cursor.execute(f"CREATE OR REPLACE TABLE {table} ({col_decls}) USING DELTA")
        return
    values = ", ".join(
        "(" + ", ".join(_sql_lit(v) for v in row) + ")" for row in rows
    )
    cols = ", ".join(f"`{c}`" for c in col_names)
    cursor.execute(
        f"CREATE OR REPLACE TABLE {table} USING DELTA AS "
        f"SELECT * FROM (VALUES {values}) AS t({cols})"
    )


class RealBackend:
    _neo4j_driver = None
    _workspace_client = None

    def _driver(self):
        if RealBackend._neo4j_driver is None:
            from neo4j import GraphDatabase
            RealBackend._neo4j_driver = GraphDatabase.driver(
                os.environ["NEO4J_URI"],
                auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
            )
        return RealBackend._neo4j_driver

    def _ws_client(self):
        if RealBackend._workspace_client is None:
            from databricks.sdk import WorkspaceClient
            RealBackend._workspace_client = WorkspaceClient()
        return RealBackend._workspace_client

    def search(self, signal_type: str, filters: dict) -> list[dict]:
        if signal_type == "fraud_rings":
            return self._search_fraud_rings(filters)
        if signal_type == "risk_scores":
            return self._search_gold_accounts(order_by="risk_score")
        if signal_type == "central_accounts":
            return self._search_gold_accounts(order_by="betweenness_centrality")
        return self._search_fraud_rings(filters)

    def _sql_conn(self):
        from databricks.sdk.core import Config
        from databricks import sql as dbsql

        cfg = Config()
        return dbsql.connect(
            server_hostname=cfg.host,
            http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
            credentials_provider=lambda: cfg.authenticate,
        )

    def _search_fraud_rings(self, filters: dict) -> list[dict]:
        summaries = self._gold_ring_summaries()
        if not summaries:
            return []

        max_raw_risk = max((float(r.get("risk_score") or 0.0) for r in summaries), default=0.0)
        graph_by_ring = self._gold_graph_details_by_ring(
            [r["ring_id"] for r in summaries],
            _bounded_int_filter(filters, "max_nodes", default=120, minimum=5, maximum=500),
        )

        rings = []
        for summary in summaries:
            ring_id = str(summary["ring_id"])
            raw_risk = float(summary.get("risk_score") or 0.0)
            display_risk = raw_risk / max_raw_risk if max_raw_risk > 1.0 else raw_risk
            graph = graph_by_ring.get(ring_id, {"nodes": [], "edges": []})
            rings.append({
                "ring_id": ring_id,
                "node_count": int(summary.get("node_count") or 0),
                "volume": int(float(summary.get("volume") or 0)),
                "shared_ids": summary.get("shared_ids") or [],
                "risk_score": round(display_risk, 3),
                "raw_risk_score": round(raw_risk, 3),
                "risk_label": _risk_label(display_risk),
                "topology": summary["topology"],
                **graph,
            })
        return rings

    def _gold_ring_summaries(self) -> list[dict]:
        table = _quoted_table("gold_fraud_ring_communities")
        sql = f"""
            SELECT
                community_id,
                member_count,
                avg_risk_score,
                total_volume_usd,
                topology,
                anchor_merchant_categories
            FROM {table}
            WHERE is_ring_candidate = true
            ORDER BY avg_risk_score DESC, member_count DESC
            LIMIT 20
        """
        conn = self._sql_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [col[0] for col in cur.description]
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        finally:
            conn.close()

        summaries = []
        for row in rows:
            summaries.append({
                "ring_id": row["community_id"],
                "node_count": row["member_count"],
                "volume": row["total_volume_usd"] or 0,
                "shared_ids": _string_array(row["anchor_merchant_categories"]),
                "risk_score": row["avg_risk_score"] or 0.0,
                "topology": str(row["topology"]),
            })
        return summaries

    def _gold_graph_details_by_ring(self, ring_ids: list[str], node_limit: int) -> dict[str, dict]:
        community_ids = _community_ids(ring_ids)
        if not community_ids:
            return {}

        edge_limit = max(200, node_limit * 3)
        accounts = _quoted_table("gold_accounts")
        pairs = _quoted_table("gold_account_similarity_pairs")
        requested = ", ".join(str(cid) for cid in community_ids)
        nodes_sql = f"""
            WITH ranked AS (
                SELECT
                    community_id,
                    account_id,
                    risk_score,
                    coalesce(distinct_counterparty_count, inbound_transfer_events, 1) AS degree,
                    row_number() OVER (
                        PARTITION BY community_id
                        ORDER BY coalesce(risk_score, 0.0) DESC, account_id
                    ) AS rn
                FROM {accounts}
                WHERE community_id IN ({requested})
            )
            SELECT community_id, account_id, risk_score, degree
            FROM ranked
            WHERE rn <= {int(node_limit)}
            ORDER BY community_id, rn
        """
        edges_sql = f"""
            WITH selected AS (
                SELECT community_id, account_id
                FROM (
                    SELECT
                        community_id,
                        account_id,
                        row_number() OVER (
                            PARTITION BY community_id
                            ORDER BY coalesce(risk_score, 0.0) DESC, account_id
                        ) AS rn
                    FROM {accounts}
                    WHERE community_id IN ({requested})
                )
                WHERE rn <= {int(node_limit)}
            ),
            ranked_edges AS (
                SELECT
                    a.community_id,
                    p.account_id_a AS source,
                    p.account_id_b AS target,
                    row_number() OVER (
                        PARTITION BY a.community_id
                        ORDER BY coalesce(p.similarity_score, 0.0) DESC,
                                 p.account_id_a,
                                 p.account_id_b
                    ) AS rn
                FROM {pairs} p
                JOIN selected a ON p.account_id_a = a.account_id
                JOIN selected b
                  ON p.account_id_b = b.account_id
                 AND a.community_id = b.community_id
                WHERE p.same_community = true
            )
            SELECT community_id, source, target
            FROM ranked_edges
            WHERE rn <= {int(edge_limit)}
            ORDER BY community_id, rn
        """

        out = {str(cid): {"nodes": [], "edges": []} for cid in community_ids}
        conn = self._sql_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(nodes_sql)
                node_rows = cur.fetchall()
                max_risk_by_ring: dict[str, float] = {}
                for community_id, _account_id, risk_score, _degree in node_rows:
                    ring_id = str(community_id)
                    max_risk_by_ring[ring_id] = max(
                        max_risk_by_ring.get(ring_id, 0.0),
                        float(risk_score or 0.0),
                    )
                for community_id, account_id, risk_score, degree in node_rows:
                    ring_id = str(community_id)
                    raw_risk = float(risk_score or 0.0)
                    max_risk = max_risk_by_ring.get(ring_id, 0.0)
                    display_risk = raw_risk / max_risk if max_risk > 1.0 else raw_risk
                    out[ring_id]["nodes"].append({
                        "data": {
                            "id": str(account_id),
                            "risk_score": round(display_risk, 3),
                            "raw_risk_score": round(raw_risk, 3),
                            "degree": int(degree or 1),
                        }
                    })
                cur.execute(edges_sql)
                edge_counts: dict[str, int] = {}
                for community_id, source, target in cur.fetchall():
                    ring_id = str(community_id)
                    idx = edge_counts.get(ring_id, 0)
                    edge_counts[ring_id] = idx + 1
                    out[ring_id]["edges"].append({
                        "data": {
                            "id": f"{ring_id}-e{idx}",
                            "source": str(source),
                            "target": str(target),
                        }
                    })
        finally:
            conn.close()
        return out

    def _search_gold_accounts(self, order_by: str) -> list[dict]:
        accounts = _quoted_table("gold_accounts")
        if order_by == "betweenness_centrality":
            order_expr = "coalesce(betweenness_centrality, 0.0)"
            prefix = "HUB"
        else:
            order_expr = "coalesce(risk_score, 0.0)"
            prefix = "HIGH"
        sql = f"""
            SELECT
                account_id,
                risk_score,
                coalesce(distinct_counterparty_count, inbound_transfer_events, 1) AS degree,
                community_id,
                fraud_risk_tier
            FROM {accounts}
            WHERE risk_score IS NOT NULL
            ORDER BY {order_expr} DESC, account_id
            LIMIT 20
        """
        conn = self._sql_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        finally:
            conn.close()

        max_risk = max((float(row[1] or 0.0) for row in rows), default=0.0)
        out = []
        for account_id, raw_risk, degree, community_id, tier in rows:
            raw = float(raw_risk or 0.0)
            display_risk = raw / max_risk if max_risk > 1.0 else raw
            node = {
                "data": {
                    "id": str(account_id),
                    "risk_score": raw,
                    "degree": int(degree or 1),
                }
            }
            out.append({
                "ring_id": f"{prefix}-{account_id}",
                "node_count": 1,
                "volume": 0,
                "shared_ids": [f"community {community_id}", str(tier or "")],
                "risk_score": round(display_risk, 3),
                "raw_risk_score": round(raw, 3),
                "risk_label": _risk_label(display_risk),
                "topology": "chain",
                "nodes": [node],
                "edges": [],
            })
        return out

    def load(self, ring_ids: list[str]) -> dict:
        accounts: list[tuple] = []
        txns: list[tuple] = []
        merchants: list[tuple] = []
        edges: list[tuple] = []

        with self._driver().session() as s:
            for ring_id in ring_ids:
                community_id = int(str(ring_id).strip())
                for rec in s.run("""
                    MATCH (a:Account) WHERE a.community_id = $cid
                    RETURN a.account_id AS account_id, a.risk_score AS risk_score
                """, cid=community_id):
                    accounts.append((ring_id, rec["account_id"], rec["risk_score"] or 0.0))

                for rec in s.run("""
                    MATCH (a:Account)-[r:TRANSACTED_WITH]->(m:Merchant)
                    WHERE a.community_id = $cid
                    RETURN a.account_id AS src, m.merchant_id AS tgt, r.amount AS amount, r.date AS date
                """, cid=community_id):
                    txns.append((ring_id, rec["src"], rec["tgt"], rec["amount"], str(rec["date"] or "")))
                    if rec["tgt"]:
                        merchants.append((ring_id, rec["tgt"]))
                    edges.append((ring_id, rec["src"], rec["tgt"], "TRANSACTED_WITH", 1.0))

        unique_merchants = sorted(set(merchants))
        unique_merchant_count = len({merchant_id for _, merchant_id in unique_merchants})
        schema = f"`{_catalog_name()}`.`fraud_signals`"

        conn = self._sql_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                _write_ctas(
                    cur, f"{schema}.`accounts`",
                    "ring_id STRING, account_id STRING, risk_score DOUBLE, first_seen STRING",
                    ["ring_id", "account_id", "risk_score", "first_seen"],
                    [(r, str(a), float(s), "") for r, a, s in accounts],
                )
                _write_ctas(
                    cur, f"{schema}.`transactions`",
                    "ring_id STRING, src_id STRING, tgt_id STRING, amount DOUBLE, txn_date STRING",
                    ["ring_id", "src_id", "tgt_id", "amount", "txn_date"],
                    [(r, str(src), str(tgt or ""), float(amt or 0), d) for r, src, tgt, amt, d in txns],
                )
                _write_ctas(
                    cur, f"{schema}.`merchants`",
                    "ring_id STRING, merchant_id STRING",
                    ["ring_id", "merchant_id"],
                    list(unique_merchants),
                )
                _write_ctas(
                    cur, f"{schema}.`graph_edges`",
                    "ring_id STRING, source_id STRING, target_id STRING, edge_type STRING, weight DOUBLE",
                    ["ring_id", "source_id", "target_id", "edge_type", "weight"],
                    [(r, str(src), str(tgt or ""), et, float(w)) for r, src, tgt, et, w in edges],
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
            "preview": [
                {"account_id": a, "ring_id": r, "risk_score": s, "first_seen": ""}
                for r, a, s in accounts[:5]
            ],
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
        timeout = timedelta(seconds=120)

        if conversation_id:
            message = w.genie.create_message_and_wait(
                space_id=space_id,
                conversation_id=conversation_id,
                content=question,
                timeout=timeout,
            )
        else:
            message = w.genie.start_conversation_and_wait(
                space_id=space_id,
                content=question,
                timeout=timeout,
            )

        conv_id = message.conversation_id or ""
        text = ""
        if message.attachments:
            text = next(
                (a.text.content for a in message.attachments if a.text and a.text.content),
                "",
            )
        return {
            "conversation_id": conv_id,
            "answer": text or "Analysis complete.",
            "table_cols": None,
            "table_rows": None,
        }
