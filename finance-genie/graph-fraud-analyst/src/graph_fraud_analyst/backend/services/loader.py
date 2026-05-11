"""Load-screen service: real Cypher → Delta materialization.

The `/api/load` endpoint pulls the selected communities (ring_ids) from Neo4j
via live Cypher, then writes three Delta tables in UC that Screen 3's Genie
Space queries:

    gold_accounts                     all :Account nodes in the loaded rings
    gold_fraud_ring_communities       per-community summary rows
    gold_account_similarity_pairs     :SIMILAR_TO edges within the loaded rings

The Delta writes use `CREATE OR REPLACE TABLE ... USING DELTA AS SELECT * FROM
VALUES (...)` via the SQL warehouse. Single-presenter demo: each Load
overwrites the previous session's data.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from databricks.sdk import WorkspaceClient
from neo4j import Driver

from ..core._config import AppConfig
from ..models import LoadOut, LoadStep, QualityCheck
from . import sql


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_ring_ids(ring_ids: list[str]) -> list[int]:
    out: list[int] = []
    for rid in ring_ids:
        try:
            out.append(int(str(rid).strip()))
        except (TypeError, ValueError):
            continue
    return out


def _step_labels() -> list[str]:
    return [
        "Fetch :Account members from Neo4j",
        "Fetch community summaries from Neo4j",
        "Fetch :SIMILAR_TO edges from Neo4j",
        "Write gold_accounts Delta table",
        "Write gold_fraud_ring_communities Delta table",
        "Write gold_account_similarity_pairs Delta table",
        "Run quality checks",
    ]


def _sql_literal(value: Any) -> str:
    """Render a Python value as a Spark SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP '{value.isoformat(sep=' ')}'"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, list):
        return f"ARRAY({', '.join(_sql_literal(v) for v in value)})"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def _rows_to_values_clause(
    rows: Iterable[dict[str, Any]], columns: list[str]
) -> str:
    row_tuples = []
    for r in rows:
        row_tuples.append(
            "(" + ", ".join(_sql_literal(r.get(c)) for c in columns) + ")"
        )
    if not row_tuples:
        return ""
    return "VALUES " + ", ".join(row_tuples)


def _write_table(
    ws: WorkspaceClient,
    config: AppConfig,
    table: str,
    columns_with_types: list[tuple[str, str]],
    rows: list[dict[str, Any]],
) -> int:
    """CREATE OR REPLACE the given table with the supplied rows."""
    columns = [c for c, _ in columns_with_types]
    qualified = f"`{config.catalog}`.`{config.schema_}`.`{table}`"
    column_decls = ", ".join(f"`{c}` {t}" for c, t in columns_with_types)

    if not rows:
        sql.execute(
            ws,
            config.warehouse_id,
            f"CREATE OR REPLACE TABLE {qualified} ({column_decls}) USING DELTA",
        )
        return 0

    values_clause = _rows_to_values_clause(rows, columns)
    column_list = ", ".join(f"`{c}`" for c in columns)
    statement = (
        f"CREATE OR REPLACE TABLE {qualified} USING DELTA AS "
        f"SELECT * FROM ({values_clause}) AS t({column_list})"
    )
    sql.execute(ws, config.warehouse_id, statement)
    return len(rows)


def _coerce_neo4j_date(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_native"):
        try:
            return value.to_native()
        except Exception:
            return None
    return value


def _normalize_accounts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for r in rows:
        r["opened_date"] = _coerce_neo4j_date(r.get("opened_date"))
    return rows


# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------


_ACCOUNTS_CYPHER = """
MATCH (a:Account) WHERE a.community_id IN $community_ids
RETURN a.account_id              AS account_id,
       a.community_id            AS community_id,
       a.risk_score              AS risk_score,
       a.betweenness_centrality  AS betweenness_centrality,
       a.similarity_score        AS similarity_score,
       a.account_type            AS account_type,
       a.region                  AS region,
       a.opened_date             AS opened_date,
       a.balance                 AS balance,
       a.holder_age              AS holder_age
ORDER BY a.community_id, a.account_id
"""

_COMMUNITIES_CYPHER = """
MATCH (a:Account) WHERE a.community_id IN $community_ids
WITH a.community_id    AS community_id,
     count(a)          AS member_count,
     avg(a.risk_score) AS avg_risk_score,
     max(a.risk_score) AS max_risk_score
OPTIONAL MATCH (b:Account)-[t:TRANSACTED_WITH]->(m:Merchant)
WHERE b.community_id = community_id
WITH community_id, member_count, avg_risk_score, max_risk_score,
     collect(DISTINCT m.category) AS categories,
     coalesce(sum(t.amount), 0)   AS total_volume_usd
RETURN community_id,
       member_count,
       avg_risk_score,
       max_risk_score,
       categories[0..3] AS anchor_merchant_categories,
       total_volume_usd,
       member_count >= 3 AS is_ring_candidate
ORDER BY community_id
"""

_SIMILARITY_CYPHER = """
MATCH (a:Account)-[s:SIMILAR_TO]->(b:Account)
WHERE a.community_id IN $community_ids
RETURN a.account_id                    AS src_account_id,
       b.account_id                    AS dst_account_id,
       s.similarity_score              AS similarity_score,
       a.community_id = b.community_id AS same_community
ORDER BY similarity_score DESC
"""


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


_ACCOUNTS_SCHEMA: list[tuple[str, str]] = [
    ("account_id", "BIGINT"),
    ("community_id", "BIGINT"),
    ("risk_score", "DOUBLE"),
    ("betweenness_centrality", "DOUBLE"),
    ("similarity_score", "DOUBLE"),
    ("account_type", "STRING"),
    ("region", "STRING"),
    ("opened_date", "DATE"),
    ("balance", "DOUBLE"),
    ("holder_age", "INT"),
]

_COMMUNITIES_SCHEMA: list[tuple[str, str]] = [
    ("community_id", "BIGINT"),
    ("member_count", "BIGINT"),
    ("avg_risk_score", "DOUBLE"),
    ("max_risk_score", "DOUBLE"),
    ("anchor_merchant_categories", "ARRAY<STRING>"),
    ("total_volume_usd", "DOUBLE"),
    ("is_ring_candidate", "BOOLEAN"),
]

_SIMILARITY_SCHEMA: list[tuple[str, str]] = [
    ("src_account_id", "BIGINT"),
    ("dst_account_id", "BIGINT"),
    ("similarity_score", "DOUBLE"),
    ("same_community", "BOOLEAN"),
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def load_rings(
    ws: WorkspaceClient,
    config: AppConfig,
    driver: Driver,
    ring_ids: list[str],
) -> LoadOut:
    target_tables = [
        f"{config.catalog}.{config.schema_}.gold_accounts",
        f"{config.catalog}.{config.schema_}.gold_fraud_ring_communities",
        f"{config.catalog}.{config.schema_}.gold_account_similarity_pairs",
    ]
    steps = [LoadStep(label=label, status="done") for label in _step_labels()]
    row_counts: dict[str, int] = {
        "gold_accounts": 0,
        "gold_fraud_ring_communities": 0,
        "gold_account_similarity_pairs": 0,
    }

    community_ids = _coerce_ring_ids(ring_ids)
    if not community_ids:
        return LoadOut(
            target_tables=target_tables,
            steps=[LoadStep(label=label, status="todo") for label in _step_labels()],
            row_counts=row_counts,
            quality_checks=[
                QualityCheck(name="At least one valid ring_id provided", passed=False),
            ],
        )

    with driver.session() as session:
        accounts = _normalize_accounts(
            session.run(_ACCOUNTS_CYPHER, community_ids=community_ids).data()
        )
        communities = session.run(
            _COMMUNITIES_CYPHER, community_ids=community_ids
        ).data()
        similarity = session.run(
            _SIMILARITY_CYPHER, community_ids=community_ids
        ).data()

    row_counts["gold_accounts"] = _write_table(
        ws, config, "gold_accounts", _ACCOUNTS_SCHEMA, accounts
    )
    row_counts["gold_fraud_ring_communities"] = _write_table(
        ws, config, "gold_fraud_ring_communities", _COMMUNITIES_SCHEMA, communities
    )
    row_counts["gold_account_similarity_pairs"] = _write_table(
        ws,
        config,
        "gold_account_similarity_pairs",
        _SIMILARITY_SCHEMA,
        similarity,
    )

    quality_checks = [
        QualityCheck(
            name="Accounts loaded",
            passed=row_counts["gold_accounts"] > 0,
        ),
        QualityCheck(
            name="Communities loaded",
            passed=row_counts["gold_fraud_ring_communities"] > 0,
        ),
        QualityCheck(
            name="All accounts have a community_id",
            passed=all(a.get("community_id") is not None for a in accounts),
        ),
        QualityCheck(
            name="All accounts have a risk_score",
            passed=all(a.get("risk_score") is not None for a in accounts),
        ),
        QualityCheck(
            name="Member counts match aggregate",
            passed=sum(int(c.get("member_count") or 0) for c in communities)
            == len(accounts),
        ),
        QualityCheck(
            name="All selected ring_ids returned",
            passed={int(c["community_id"]) for c in communities if c.get("community_id") is not None}
            == set(community_ids),
        ),
    ]

    return LoadOut(
        target_tables=target_tables,
        steps=steps,
        row_counts=row_counts,
        quality_checks=quality_checks,
    )
