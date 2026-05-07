"""Data backend for Finance Genie Client."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.serving import ExternalFunctionRequestHttpMethod


CATALOG = os.getenv("CATALOG", "graph-enriched-lakehouse")
SCHEMA = os.getenv("SCHEMA", "graph-enriched-schema")
MCP_SCHEMA_CONNECTION_NAME = os.getenv("MCP_SCHEMA_CONNECTION_NAME", "")
MCP_SCHEMA_PATH = os.getenv("MCP_SCHEMA_PATH", "/")
MCP_SCHEMA_TOOL_NAME = os.getenv("MCP_SCHEMA_TOOL_NAME", "get_full_schema")


@dataclass(frozen=True)
class QuestionPair:
    key: str
    title: str
    before_question: str
    after_question: str
    before_takeaway: str
    after_takeaway: str
    before_label: str
    after_label: str


QUESTION_PAIRS: tuple[QuestionPair, ...] = (
    QuestionPair(
        key="merchant_concentration",
        title="Merchant Concentration",
        before_question=(
            "Which merchants are most commonly transacted with by the top 10% "
            "of accounts by total dollar amount spent across merchants?"
        ),
        after_question=(
            "Which merchants show the highest concentration of ring-candidate "
            "transactions relative to the overall book?"
        ),
        before_takeaway=(
            "The Silver catalog can rank merchant popularity for high-spend "
            "accounts, but it has no structural cohort to compare against."
        ),
        after_takeaway=(
            "The Gold catalog can compare ring-candidate share to the book "
            "baseline and turn merchant popularity into triage signal."
        ),
        before_label="Top merchants among high-spend accounts",
        after_label="Top merchants by ring-candidate overrepresentation",
    ),
    QuestionPair(
        key="review_workload",
        title="Investigator Review Workload",
        before_question=(
            "How many accounts are in the top 10% by transfer volume, and what "
            "is the regional breakdown of that workload?"
        ),
        after_question=(
            "How many accounts would need investigator review if the bar is "
            "high risk tier, and what is the regional breakdown?"
        ),
        before_takeaway=(
            "The Silver catalog can size a volume-based review queue, which is "
            "useful operationally but mixes whales with structurally risky accounts."
        ),
        after_takeaway=(
            "The Gold catalog can size the review queue by graph-derived risk "
            "tier, giving operations a defensible workload estimate."
        ),
        before_label="Top-transfer workload by region",
        after_label="High-risk workload by region",
    ),
    QuestionPair(
        key="flow_structure",
        title="Transfer Flow Structure",
        before_question=(
            "What fraction of total transfer volume flows between accounts that "
            "have transacted together 5 or more times?"
        ),
        after_question=(
            "What fraction of transfer volume flows between accounts in the "
            "same community versus across communities?"
        ),
        before_takeaway=(
            "The Silver catalog can measure repeat pair behavior, but a pair is "
            "not a community and misses broader coordination."
        ),
        after_takeaway=(
            "The Gold catalog can group transfers by Louvain community, making "
            "closed-loop movement measurable as ordinary SQL."
        ),
        before_label="Repeat-pair transfer volume",
        after_label="Same-community transfer volume",
    ),
    QuestionPair(
        key="book_exposure",
        title="Book Exposure",
        before_question=(
            "For the top 10% of accounts by transfer volume, what is the total "
            "balance held and what share of the book do they represent?"
        ),
        after_question=(
            "What is the total account balance held by high-risk tier accounts, "
            "and what share of the total book does that represent by region?"
        ),
        before_takeaway=(
            "The Silver catalog can put dollars around an activity proxy, but "
            "the proxy is not a structural risk segment."
        ),
        after_takeaway=(
            "The Gold catalog can quantify exposure by a graph-derived risk "
            "tier that Genie can filter and group like any other dimension."
        ),
        before_label="Balance exposure for high-transfer accounts",
        after_label="Balance exposure for high-risk accounts",
    ),
)


def fqn(table: str) -> str:
    """Return a fully qualified table name."""
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"


@st.cache_resource(ttl=600)
def get_connection():
    """Create a cached Databricks SQL connection."""
    warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
    if not warehouse_id:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. Add a SQL warehouse resource "
            "to the Databricks App or set the variable for local development."
        )

    profile = os.getenv("DATABRICKS_CONFIG_PROFILE")
    try:
        cfg = Config(profile=profile) if profile else Config()
    except Exception as exc:
        raise RuntimeError(
            "Databricks credentials are not configured for local development. "
            "DATABRICKS_WAREHOUSE_ID only selects the SQL warehouse; it does "
            "not authenticate. Add DATABRICKS_CONFIG_PROFILE=<profile> to "
            ".env.local when using ~/.databrickscfg, or set DATABRICKS_HOST "
            "plus a supported credential such as DATABRICKS_TOKEN."
        ) from exc

    return sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        credentials_provider=lambda: cfg.authenticate,
    )


def query(sql_text: str) -> pd.DataFrame:
    """Execute SQL and return a pandas DataFrame."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql_text)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=columns)


@st.cache_resource(ttl=600)
def get_workspace_client() -> WorkspaceClient:
    """Create a cached Databricks SDK workspace client."""
    profile = os.getenv("DATABRICKS_CONFIG_PROFILE")
    return WorkspaceClient(profile=profile) if profile else WorkspaceClient()


def mcp_schema_is_configured() -> bool:
    """Return whether MCP schema retrieval has enough configuration to run."""
    return bool(MCP_SCHEMA_CONNECTION_NAME)


def _response_header(response: Any, header_name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    return headers.get(header_name) or headers.get(header_name.lower())


def _response_json(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "json"):
        return response.json()
    if hasattr(response, "as_dict"):
        return response.as_dict()
    raise TypeError(f"Unsupported MCP response type: {type(response).__name__}")


def _mcp_http_request(
    connection_name: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Any:
    return get_workspace_client().serving_endpoints.http_request(
        conn=connection_name,
        method=ExternalFunctionRequestHttpMethod.POST,
        path=MCP_SCHEMA_PATH,
        headers=headers or {"Content-Type": "application/json"},
        json=payload,
    )


def init_mcp_schema_session(connection_name: str | None = None) -> str | None:
    """Initialize an MCP JSON-RPC session through a UC HTTP connection."""
    connection = connection_name or MCP_SCHEMA_CONNECTION_NAME
    if not connection:
        raise RuntimeError("MCP_SCHEMA_CONNECTION_NAME is not set.")

    response = _mcp_http_request(
        connection,
        {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {},
        },
    )
    return _response_header(response, "mcp-session-id")


def mcp_schema_request(
    method: str,
    params: dict[str, Any] | None = None,
    request_id: str = "request-1",
    connection_name: str | None = None,
) -> dict[str, Any]:
    """Send one JSON-RPC request to the configured MCP schema server."""
    connection = connection_name or MCP_SCHEMA_CONNECTION_NAME
    if not connection:
        raise RuntimeError("MCP_SCHEMA_CONNECTION_NAME is not set.")

    session_id = init_mcp_schema_session(connection)
    headers = {"Content-Type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    response = _mcp_http_request(
        connection,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            **({"params": params} if params is not None else {}),
        },
        headers=headers,
    )
    return _response_json(response)


@st.cache_data(ttl=300)
def list_mcp_schema_tools() -> list[dict[str, Any]]:
    """List tools exposed by the configured MCP schema server."""
    response = mcp_schema_request("tools/list", request_id="tools-list-1")
    if response.get("error"):
        raise RuntimeError(response["error"])
    tools = response.get("result", {}).get("tools", [])
    return tools if isinstance(tools, list) else []


@st.cache_data(ttl=300)
def call_mcp_schema_tool(
    tool_name: str = MCP_SCHEMA_TOOL_NAME,
    catalog: str = CATALOG,
    schema: str = SCHEMA,
) -> dict[str, Any]:
    """Call the configured MCP tool that returns the lakehouse schema."""
    response = mcp_schema_request(
        "tools/call",
        params={
            "name": tool_name,
            "arguments": {"catalog": catalog, "schema": schema},
        },
        request_id="schema-1",
    )
    if response.get("error"):
        raise RuntimeError(response["error"])
    return response


def _extract_tool_payload(response: dict[str, Any]) -> Any:
    result = response.get("result", response)
    if isinstance(result, dict):
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list) and content:
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") in {None, "text"}
            ]
            text = "\n".join(part for part in text_parts if part).strip()
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
    return result


def _find_payload_list(payload: Any, names: tuple[str, ...]) -> list[Any]:
    if not isinstance(payload, dict):
        return []
    for name in names:
        value = payload.get(name)
        if isinstance(value, list):
            return value
    for nested_name in ("schema", "data", "result"):
        nested = payload.get(nested_name)
        found = _find_payload_list(nested, names)
        if found:
            return found
    return []


def _record_value(record: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        value = record.get(name)
        if value is not None:
            return value
    return default


def _split_table_name(table: dict[str, Any]) -> tuple[str, str, str]:
    full_name = str(_record_value(table, "full_name", "fullName", default=""))
    if full_name.count(".") >= 2:
        catalog, schema, name = full_name.rsplit(".", 2)
        return catalog.strip("`"), schema.strip("`"), name.strip("`")
    return (
        str(_record_value(table, "catalog", "catalog_name", default=CATALOG)),
        str(_record_value(table, "schema", "schema_name", "database", default=SCHEMA)),
        str(_record_value(table, "name", "table_name", "tableName", default=full_name)),
    )


def normalize_mcp_schema_response(response: dict[str, Any]) -> dict[str, Any]:
    """Convert common MCP schema payload shapes into display-ready frames."""
    payload = _extract_tool_payload(response)
    tables = _find_payload_list(payload, ("tables", "table_schema", "objects"))
    top_level_columns = _find_payload_list(payload, ("columns",))
    relationships = _find_payload_list(
        payload,
        ("relationships", "relations", "foreign_keys", "foreignKeys"),
    )

    table_rows: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []

    for table in tables:
        if not isinstance(table, dict):
            continue
        catalog, schema, table_name = _split_table_name(table)
        table_columns = _record_value(table, "columns", "fields", default=[])
        if not isinstance(table_columns, list):
            table_columns = []
        table_rows.append(
            {
                "Catalog": catalog,
                "Schema": schema,
                "Table": table_name,
                "Type": _record_value(table, "type", "table_type", "tableType"),
                "Comment": _record_value(table, "comment", "description"),
                "Column count": len(table_columns) if table_columns else None,
            }
        )
        for column in table_columns:
            if not isinstance(column, dict):
                continue
            column_rows.append(
                {
                    "Catalog": catalog,
                    "Schema": schema,
                    "Table": table_name,
                    "Column": _record_value(column, "name", "column_name", "columnName"),
                    "Type": _record_value(column, "type", "data_type", "dataType"),
                    "Nullable": _record_value(column, "nullable", "is_nullable", "isNullable"),
                    "Comment": _record_value(column, "comment", "description"),
                }
            )

    for column in top_level_columns:
        if not isinstance(column, dict):
            continue
        catalog = _record_value(column, "catalog", "catalog_name", default=CATALOG)
        schema = _record_value(column, "schema", "schema_name", default=SCHEMA)
        table_name = _record_value(column, "table", "table_name", "tableName")
        column_rows.append(
            {
                "Catalog": catalog,
                "Schema": schema,
                "Table": table_name,
                "Column": _record_value(column, "name", "column_name", "columnName"),
                "Type": _record_value(column, "type", "data_type", "dataType"),
                "Nullable": _record_value(column, "nullable", "is_nullable", "isNullable"),
                "Comment": _record_value(column, "comment", "description"),
            }
        )

    relationship_rows = [
        item for item in relationships if isinstance(item, dict)
    ]

    return {
        "payload": payload,
        "tables": pd.DataFrame(table_rows),
        "columns": pd.DataFrame(column_rows),
        "relationships": pd.DataFrame(relationship_rows),
    }


def _limit(value: int, default: int = 10, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


@st.cache_data(ttl=300)
def dataset_snapshot() -> pd.DataFrame:
    return query(
        f"""
        SELECT 'Silver accounts' AS metric, COUNT(*) AS value FROM {fqn('accounts')}
        UNION ALL
        SELECT 'Silver transactions' AS metric, COUNT(*) AS value FROM {fqn('transactions')}
        UNION ALL
        SELECT 'Silver transfers' AS metric, COUNT(*) AS value FROM {fqn('account_links')}
        UNION ALL
        SELECT 'Gold accounts' AS metric, COUNT(*) AS value FROM {fqn('gold_accounts')}
        UNION ALL
        SELECT 'High-risk Gold accounts' AS metric, COUNT(*) AS value
        FROM {fqn('gold_accounts')}
        WHERE fraud_risk_tier = 'high'
        UNION ALL
        SELECT 'Ring-candidate communities' AS metric, COUNT(*) AS value
        FROM {fqn('gold_fraud_ring_communities')}
        WHERE is_ring_candidate = true
        """
    )


@st.cache_data(ttl=300)
def merchant_popularity_before(top_n: int = 10) -> pd.DataFrame:
    top_n = _limit(top_n)
    return query(
        f"""
        WITH account_spend AS (
            SELECT account_id, SUM(amount) AS total_spend
            FROM {fqn('transactions')}
            GROUP BY account_id
        ),
        cutoff AS (
            SELECT percentile_approx(total_spend, 0.9) AS min_top_spend
            FROM account_spend
        ),
        top_accounts AS (
            SELECT account_id
            FROM account_spend
            CROSS JOIN cutoff
            WHERE total_spend >= min_top_spend
        )
        SELECT
            m.merchant_name,
            m.category,
            COUNT(*) AS transaction_count,
            COUNT(DISTINCT t.account_id) AS account_count,
            ROUND(SUM(t.amount), 2) AS total_amount
        FROM {fqn('transactions')} t
        JOIN top_accounts ta ON ta.account_id = t.account_id
        JOIN {fqn('merchants')} m ON m.merchant_id = t.merchant_id
        GROUP BY m.merchant_name, m.category
        ORDER BY transaction_count DESC, total_amount DESC
        LIMIT {top_n}
        """
    )


@st.cache_data(ttl=300)
def merchant_concentration_after(top_n: int = 10) -> pd.DataFrame:
    top_n = _limit(top_n)
    return query(
        f"""
        WITH tx AS (
            SELECT
                t.txn_id,
                t.account_id,
                t.merchant_id,
                t.amount,
                CASE WHEN g.fraud_risk_tier = 'high' THEN 1 ELSE 0 END AS is_high_risk
            FROM {fqn('transactions')} t
            JOIN {fqn('gold_accounts')} g ON g.account_id = t.account_id
        ),
        baseline AS (
            SELECT AVG(is_high_risk) AS baseline_ring_share
            FROM tx
        )
        SELECT
            m.merchant_name,
            m.category,
            COUNT(*) AS transaction_count,
            SUM(is_high_risk) AS ring_candidate_transactions,
            COUNT(DISTINCT CASE WHEN is_high_risk = 1 THEN tx.account_id END) AS ring_candidate_accounts,
            ROUND(AVG(is_high_risk) * 100, 2) AS ring_transaction_share_pct,
            ROUND(MAX(baseline_ring_share) * 100, 2) AS book_baseline_pct,
            ROUND(AVG(is_high_risk) / NULLIF(MAX(baseline_ring_share), 0), 2) AS overrepresentation_index
        FROM tx
        JOIN {fqn('merchants')} m ON m.merchant_id = tx.merchant_id
        CROSS JOIN baseline
        GROUP BY m.merchant_name, m.category
        HAVING SUM(is_high_risk) > 0
        ORDER BY overrepresentation_index DESC, ring_candidate_transactions DESC
        LIMIT {top_n}
        """
    )


@st.cache_data(ttl=300)
def review_workload_before() -> pd.DataFrame:
    return query(
        f"""
        WITH account_transfer_volume AS (
            SELECT account_id, SUM(amount) AS transfer_volume
            FROM (
                SELECT src_account_id AS account_id, amount FROM {fqn('account_links')}
                UNION ALL
                SELECT dst_account_id AS account_id, amount FROM {fqn('account_links')}
            )
            GROUP BY account_id
        ),
        cutoff AS (
            SELECT percentile_approx(transfer_volume, 0.9) AS min_top_volume
            FROM account_transfer_volume
        )
        SELECT
            a.region,
            COUNT(*) AS review_accounts,
            ROUND(SUM(a.balance), 2) AS review_balance,
            ROUND(AVG(v.transfer_volume), 2) AS avg_transfer_volume
        FROM account_transfer_volume v
        JOIN cutoff c ON v.transfer_volume >= c.min_top_volume
        JOIN {fqn('accounts')} a ON a.account_id = v.account_id
        GROUP BY a.region
        ORDER BY review_accounts DESC, review_balance DESC
        """
    )


@st.cache_data(ttl=300)
def review_workload_after() -> pd.DataFrame:
    return query(
        f"""
        SELECT
            region,
            COUNT(*) AS review_accounts,
            ROUND(SUM(balance), 2) AS review_balance,
            ROUND(AVG(risk_score), 6) AS avg_risk_score,
            COUNT(DISTINCT community_id) AS communities
        FROM {fqn('gold_accounts')}
        WHERE fraud_risk_tier = 'high'
        GROUP BY region
        ORDER BY review_accounts DESC, review_balance DESC
        """
    )


@st.cache_data(ttl=300)
def flow_structure_before() -> pd.DataFrame:
    return query(
        f"""
        WITH pair_counts AS (
            SELECT
                LEAST(src_account_id, dst_account_id) AS account_a,
                GREATEST(src_account_id, dst_account_id) AS account_b,
                COUNT(*) AS transfer_events
            FROM {fqn('account_links')}
            GROUP BY LEAST(src_account_id, dst_account_id), GREATEST(src_account_id, dst_account_id)
        ),
        labeled_transfers AS (
            SELECT
                CASE WHEN p.transfer_events >= 5 THEN 'repeat_pair' ELSE 'other_pair' END AS segment,
                l.amount
            FROM {fqn('account_links')} l
            JOIN pair_counts p
              ON p.account_a = LEAST(l.src_account_id, l.dst_account_id)
             AND p.account_b = GREATEST(l.src_account_id, l.dst_account_id)
        ),
        totals AS (
            SELECT SUM(amount) AS book_transfer_volume FROM labeled_transfers
        )
        SELECT
            segment,
            COUNT(*) AS transfer_events,
            ROUND(SUM(amount), 2) AS transfer_volume,
            ROUND(SUM(amount) / MAX(book_transfer_volume) * 100, 2) AS transfer_volume_share_pct
        FROM labeled_transfers
        CROSS JOIN totals
        GROUP BY segment
        ORDER BY transfer_volume DESC
        """
    )


@st.cache_data(ttl=300)
def flow_structure_after() -> pd.DataFrame:
    return query(
        f"""
        WITH labeled_transfers AS (
            SELECT
                CASE
                    WHEN src.community_id IS NOT NULL
                     AND src.community_id = dst.community_id
                    THEN 'same_community'
                    ELSE 'cross_community'
                END AS segment,
                l.amount
            FROM {fqn('account_links')} l
            JOIN {fqn('gold_accounts')} src ON src.account_id = l.src_account_id
            JOIN {fqn('gold_accounts')} dst ON dst.account_id = l.dst_account_id
        ),
        totals AS (
            SELECT SUM(amount) AS book_transfer_volume FROM labeled_transfers
        )
        SELECT
            segment,
            COUNT(*) AS transfer_events,
            ROUND(SUM(amount), 2) AS transfer_volume,
            ROUND(SUM(amount) / MAX(book_transfer_volume) * 100, 2) AS transfer_volume_share_pct
        FROM labeled_transfers
        CROSS JOIN totals
        GROUP BY segment
        ORDER BY transfer_volume DESC
        """
    )


@st.cache_data(ttl=300)
def book_exposure_before() -> pd.DataFrame:
    return query(
        f"""
        WITH account_transfer_volume AS (
            SELECT account_id, SUM(amount) AS transfer_volume
            FROM (
                SELECT src_account_id AS account_id, amount FROM {fqn('account_links')}
                UNION ALL
                SELECT dst_account_id AS account_id, amount FROM {fqn('account_links')}
            )
            GROUP BY account_id
        ),
        cutoff AS (
            SELECT percentile_approx(transfer_volume, 0.9) AS min_top_volume
            FROM account_transfer_volume
        ),
        book AS (
            SELECT region, SUM(balance) AS regional_book_balance
            FROM {fqn('accounts')}
            GROUP BY region
        )
        SELECT
            a.region,
            COUNT(*) AS accounts,
            ROUND(SUM(a.balance), 2) AS segment_balance,
            ROUND(MAX(b.regional_book_balance), 2) AS regional_book_balance,
            ROUND(SUM(a.balance) / MAX(b.regional_book_balance) * 100, 2) AS regional_book_share_pct
        FROM account_transfer_volume v
        JOIN cutoff c ON v.transfer_volume >= c.min_top_volume
        JOIN {fqn('accounts')} a ON a.account_id = v.account_id
        JOIN book b ON b.region = a.region
        GROUP BY a.region
        ORDER BY segment_balance DESC
        """
    )


@st.cache_data(ttl=300)
def book_exposure_after() -> pd.DataFrame:
    return query(
        f"""
        WITH book AS (
            SELECT region, SUM(balance) AS regional_book_balance
            FROM {fqn('gold_accounts')}
            GROUP BY region
        )
        SELECT
            g.region,
            COUNT(*) AS accounts,
            ROUND(SUM(g.balance), 2) AS segment_balance,
            ROUND(MAX(b.regional_book_balance), 2) AS regional_book_balance,
            ROUND(SUM(g.balance) / MAX(b.regional_book_balance) * 100, 2) AS regional_book_share_pct,
            COUNT(DISTINCT g.community_id) AS communities
        FROM {fqn('gold_accounts')} g
        JOIN book b ON b.region = g.region
        WHERE g.fraud_risk_tier = 'high'
        GROUP BY g.region
        ORDER BY segment_balance DESC
        """
    )


PAIR_QUERY_FUNCTIONS: dict[str, tuple[Callable[[], pd.DataFrame], Callable[[], pd.DataFrame]]] = {
    "merchant_concentration": (
        lambda: merchant_popularity_before(10),
        lambda: merchant_concentration_after(10),
    ),
    "review_workload": (review_workload_before, review_workload_after),
    "flow_structure": (flow_structure_before, flow_structure_after),
    "book_exposure": (book_exposure_before, book_exposure_after),
}


def run_pair(pair_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the before and after SQL functions for a curated pair."""
    if pair_key not in PAIR_QUERY_FUNCTIONS:
        raise KeyError(f"Unknown question pair: {pair_key}")
    before_fn, after_fn = PAIR_QUERY_FUNCTIONS[pair_key]
    return before_fn(), after_fn()


@st.cache_data(ttl=300)
def question_surface() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Question type": "Merchant popularity",
                "Before catalog": "Answerable",
                "After catalog": "Answerable",
                "Why it matters": "Standard merchant ranking remains available.",
            },
            {
                "Question type": "Ring-candidate merchant concentration",
                "Before catalog": "Not available",
                "After catalog": "Answerable",
                "Why it matters": "Requires `fraud_risk_tier` or `is_ring_community`.",
            },
            {
                "Question type": "Community-level transfer circulation",
                "Before catalog": "Proxy only",
                "After catalog": "Answerable",
                "Why it matters": "Requires `community_id` from Louvain.",
            },
            {
                "Question type": "Investigator workload by risk tier",
                "Before catalog": "Proxy only",
                "After catalog": "Answerable",
                "Why it matters": "Requires graph-derived risk segmentation.",
            },
            {
                "Question type": "Shared-merchant account similarity",
                "Before catalog": "Manual query required",
                "After catalog": "Answerable",
                "Why it matters": "Requires Node Similarity scores in Gold.",
            },
            {
                "Question type": "Book exposure by structural risk",
                "Before catalog": "Proxy only",
                "After catalog": "Answerable",
                "Why it matters": "Transforms graph signal into finance impact.",
            },
        ]
    )


def graph_schema_elements() -> dict[str, list[dict[str, dict[str, object]]]]:
    """Return the static graph schema shown in the schema page."""
    return {
        "nodes": [
            {
                "data": {
                    "id": "account",
                    "label": "ACCOUNT",
                    "name": "Account",
                    "table": "accounts, gold_accounts",
                    "description": "Customer account node enriched with GDS features.",
                }
            },
            {
                "data": {
                    "id": "merchant",
                    "label": "MERCHANT",
                    "name": "Merchant",
                    "table": "merchants",
                    "description": "Merchant dimension connected through card transactions.",
                }
            },
            {
                "data": {
                    "id": "community",
                    "label": "COMMUNITY",
                    "name": "Community",
                    "table": "gold_fraud_ring_communities",
                    "description": "Derived Louvain community summary.",
                }
            },
            {
                "data": {
                    "id": "pagerank",
                    "label": "ALGORITHM",
                    "name": "PageRank",
                    "description": "Measures transfer-network centrality.",
                }
            },
            {
                "data": {
                    "id": "louvain",
                    "label": "ALGORITHM",
                    "name": "Louvain",
                    "description": "Partitions densely connected transfer communities.",
                }
            },
            {
                "data": {
                    "id": "node_similarity",
                    "label": "ALGORITHM",
                    "name": "Node Similarity",
                    "description": "Measures shared-merchant neighborhood overlap.",
                }
            },
            {
                "data": {
                    "id": "risk_features",
                    "label": "FEATURE",
                    "name": "Risk features",
                    "fields": "risk_score, fraud_risk_tier, is_ring_community",
                }
            },
            {
                "data": {
                    "id": "similarity_pairs",
                    "label": "TABLE",
                    "name": "Similarity pairs",
                    "table": "gold_account_similarity_pairs",
                }
            },
        ],
        "edges": [
            {
                "data": {
                    "id": "account-transfer",
                    "label": "TRANSFERRED_TO",
                    "source": "account",
                    "target": "account",
                    "table": "account_links",
                }
            },
            {
                "data": {
                    "id": "account-merchant",
                    "label": "TRANSACTED_WITH",
                    "source": "account",
                    "target": "merchant",
                    "table": "transactions",
                }
            },
            {
                "data": {
                    "id": "account-community",
                    "label": "IN_COMMUNITY",
                    "source": "account",
                    "target": "community",
                    "field": "gold_accounts.community_id",
                }
            },
            {
                "data": {
                    "id": "account-similar",
                    "label": "SIMILAR_TO",
                    "source": "account",
                    "target": "account",
                    "table": "gold_account_similarity_pairs",
                }
            },
            {
                "data": {
                    "id": "pagerank-risk",
                    "label": "ADDS",
                    "source": "pagerank",
                    "target": "risk_features",
                    "fields": "risk_score",
                }
            },
            {
                "data": {
                    "id": "louvain-community",
                    "label": "DERIVES",
                    "source": "louvain",
                    "target": "community",
                    "fields": "community_id, community_size",
                }
            },
            {
                "data": {
                    "id": "louvain-risk",
                    "label": "ADDS",
                    "source": "louvain",
                    "target": "risk_features",
                    "fields": "is_ring_community, fraud_risk_tier",
                }
            },
            {
                "data": {
                    "id": "node-similarity-pairs",
                    "label": "WRITES",
                    "source": "node_similarity",
                    "target": "similarity_pairs",
                    "fields": "similarity_score, same_community",
                }
            },
        ],
    }


def graph_schema_tables() -> pd.DataFrame:
    """Return the Silver and Gold table roles in the graph model."""
    return pd.DataFrame(
        [
            {
                "Layer": "Silver",
                "Table": "accounts",
                "Graph role": "Account nodes",
                "Key fields": "account_id, account_type, region, balance",
            },
            {
                "Layer": "Silver",
                "Table": "merchants",
                "Graph role": "Merchant nodes",
                "Key fields": "merchant_id, merchant_name, category",
            },
            {
                "Layer": "Silver",
                "Table": "transactions",
                "Graph role": "Account-to-merchant edges",
                "Key fields": "account_id, merchant_id, amount",
            },
            {
                "Layer": "Silver",
                "Table": "account_links",
                "Graph role": "Directed account-to-account transfer edges",
                "Key fields": "src_account_id, dst_account_id, amount",
            },
            {
                "Layer": "Gold",
                "Table": "gold_accounts",
                "Graph role": "Account nodes with GDS features",
                "Key fields": "risk_score, community_id, fraud_risk_tier",
            },
            {
                "Layer": "Gold",
                "Table": "gold_account_similarity_pairs",
                "Graph role": "Account-to-account similarity edges",
                "Key fields": "account_id_a, account_id_b, similarity_score",
            },
            {
                "Layer": "Gold",
                "Table": "gold_fraud_ring_communities",
                "Graph role": "Community summary nodes",
                "Key fields": "community_id, member_count, is_ring_candidate",
            },
        ]
    )


def gds_enrichment_columns() -> pd.DataFrame:
    """Return the GDS outputs materialized into Gold tables."""
    return pd.DataFrame(
        [
            {
                "Algorithm": "PageRank",
                "Gold artifact": "gold_accounts.risk_score",
                "Graph meaning": "Transfer-network centrality for each account.",
                "Genie use": "Rank and filter accounts by structural influence.",
            },
            {
                "Algorithm": "Louvain",
                "Gold artifact": "gold_accounts.community_id",
                "Graph meaning": "Dense account-transfer community assignment.",
                "Genie use": "Group transfers, exposure, and workload by community.",
            },
            {
                "Algorithm": "Louvain",
                "Gold artifact": "gold_fraud_ring_communities",
                "Graph meaning": "One row per derived community with risk rollups.",
                "Genie use": "Ask community-level ring-candidate questions.",
            },
            {
                "Algorithm": "Node Similarity",
                "Gold artifact": "gold_accounts.similarity_score",
                "Graph meaning": "Highest shared-merchant similarity for the account.",
                "Genie use": "Find accounts with similar merchant behavior.",
            },
            {
                "Algorithm": "Node Similarity",
                "Gold artifact": "gold_account_similarity_pairs",
                "Graph meaning": "Account pairs connected by shared-merchant overlap.",
                "Genie use": "Rank pairs and compare similarity inside communities.",
            },
            {
                "Algorithm": "Derived rule",
                "Gold artifact": "fraud_risk_tier, is_ring_community",
                "Graph meaning": "Risk segment derived from community size and centrality.",
                "Genie use": "Filter high-risk accounts with ordinary SQL predicates.",
            },
        ]
    )


def _native_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return value.item()
    return value


def _native_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {key: _native_value(value) for key, value in row.items()}
        for row in frame.to_dict("records")
    ]


@st.cache_data(ttl=300)
def ring_candidate_communities(limit: int = 25) -> pd.DataFrame:
    limit = _limit(limit, default=25, maximum=100)
    return query(
        f"""
        SELECT
            community_id,
            member_count,
            ROUND(avg_risk_score, 6) AS avg_risk_score,
            ROUND(avg_similarity_score, 6) AS avg_similarity_score,
            high_risk_member_count,
            top_account_id
        FROM {fqn('gold_fraud_ring_communities')}
        WHERE is_ring_candidate = true
        ORDER BY avg_risk_score DESC, member_count DESC
        LIMIT {limit}
        """
    )


@st.cache_data(ttl=300)
def graph_sample_elements(
    community_id: int,
    account_limit: int = 60,
    transfer_limit: int = 120,
    merchant_limit: int = 20,
    similarity_limit: int = 60,
) -> dict[str, list[dict[str, dict[str, object]]]]:
    """Build a bounded graph sample for one enriched community."""
    community_id = int(community_id)
    account_limit = _limit(account_limit, default=60, maximum=100)
    transfer_limit = _limit(transfer_limit, default=120, maximum=300)
    merchant_limit = _limit(merchant_limit, default=20, maximum=50)
    similarity_limit = _limit(similarity_limit, default=60, maximum=200)

    accounts = query(
        f"""
        SELECT
            account_id,
            account_hash,
            region,
            ROUND(balance, 2) AS balance,
            ROUND(risk_score, 6) AS risk_score,
            ROUND(similarity_score, 6) AS similarity_score,
            community_risk_rank,
            fraud_risk_tier
        FROM {fqn('gold_accounts')}
        WHERE community_id = {community_id}
        ORDER BY community_risk_rank ASC, risk_score DESC, account_id ASC
        LIMIT {account_limit}
        """
    )
    if accounts.empty:
        return {"nodes": [], "edges": []}

    community = query(
        f"""
        SELECT
            community_id,
            member_count,
            ROUND(avg_risk_score, 6) AS avg_risk_score,
            ROUND(avg_similarity_score, 6) AS avg_similarity_score,
            high_risk_member_count,
            is_ring_candidate,
            top_account_id
        FROM {fqn('gold_fraud_ring_communities')}
        WHERE community_id = {community_id}
        LIMIT 1
        """
    )

    transfers = query(
        f"""
        WITH selected AS (
            SELECT account_id
            FROM {fqn('gold_accounts')}
            WHERE community_id = {community_id}
            ORDER BY community_risk_rank ASC, risk_score DESC, account_id ASC
            LIMIT {account_limit}
        )
        SELECT
            l.src_account_id,
            l.dst_account_id,
            COUNT(*) AS transfer_events,
            ROUND(SUM(l.amount), 2) AS transfer_amount
        FROM {fqn('account_links')} l
        JOIN selected src ON src.account_id = l.src_account_id
        JOIN selected dst ON dst.account_id = l.dst_account_id
        GROUP BY l.src_account_id, l.dst_account_id
        ORDER BY transfer_amount DESC, transfer_events DESC
        LIMIT {transfer_limit}
        """
    )

    merchants = query(
        f"""
        WITH selected AS (
            SELECT account_id
            FROM {fqn('gold_accounts')}
            WHERE community_id = {community_id}
            ORDER BY community_risk_rank ASC, risk_score DESC, account_id ASC
            LIMIT {account_limit}
        )
        SELECT
            m.merchant_id,
            m.merchant_name,
            m.category,
            COUNT(*) AS transaction_events,
            ROUND(SUM(t.amount), 2) AS transaction_amount
        FROM {fqn('transactions')} t
        JOIN selected s ON s.account_id = t.account_id
        JOIN {fqn('merchants')} m ON m.merchant_id = t.merchant_id
        GROUP BY m.merchant_id, m.merchant_name, m.category
        ORDER BY transaction_events DESC, transaction_amount DESC
        LIMIT {merchant_limit}
        """
    )

    account_merchants = query(
        f"""
        WITH selected AS (
            SELECT account_id
            FROM {fqn('gold_accounts')}
            WHERE community_id = {community_id}
            ORDER BY community_risk_rank ASC, risk_score DESC, account_id ASC
            LIMIT {account_limit}
        ),
        top_merchants AS (
            SELECT t.merchant_id
            FROM {fqn('transactions')} t
            JOIN selected s ON s.account_id = t.account_id
            GROUP BY t.merchant_id
            ORDER BY COUNT(*) DESC, SUM(t.amount) DESC
            LIMIT {merchant_limit}
        )
        SELECT
            t.account_id,
            t.merchant_id,
            COUNT(*) AS transaction_events,
            ROUND(SUM(t.amount), 2) AS transaction_amount
        FROM {fqn('transactions')} t
        JOIN selected s ON s.account_id = t.account_id
        JOIN top_merchants tm ON tm.merchant_id = t.merchant_id
        GROUP BY t.account_id, t.merchant_id
        ORDER BY transaction_events DESC, transaction_amount DESC
        LIMIT {account_limit * 2}
        """
    )

    similarities = query(
        f"""
        WITH selected AS (
            SELECT account_id
            FROM {fqn('gold_accounts')}
            WHERE community_id = {community_id}
            ORDER BY community_risk_rank ASC, risk_score DESC, account_id ASC
            LIMIT {account_limit}
        )
        SELECT
            p.account_id_a,
            p.account_id_b,
            ROUND(p.similarity_score, 6) AS similarity_score,
            p.same_community
        FROM {fqn('gold_account_similarity_pairs')} p
        JOIN selected a ON a.account_id = p.account_id_a
        JOIN selected b ON b.account_id = p.account_id_b
        ORDER BY p.similarity_score DESC
        LIMIT {similarity_limit}
        """
    )

    nodes: list[dict[str, dict[str, object]]] = []
    edges: list[dict[str, dict[str, object]]] = []

    community_row = _native_records(community)[0] if not community.empty else {}
    nodes.append(
        {
            "data": {
                "id": f"community:{community_id}",
                "label": "COMMUNITY",
                "name": f"Community {community_id}",
                **community_row,
            }
        }
    )

    for row in _native_records(accounts):
        account_id = row["account_id"]
        nodes.append(
            {
                "data": {
                    "id": f"account:{account_id}",
                    "label": "ACCOUNT",
                    "name": f"Account {account_id}",
                    **row,
                }
            }
        )
        edges.append(
            {
                "data": {
                    "id": f"community:{community_id}:account:{account_id}",
                    "label": "IN_COMMUNITY",
                    "source": f"account:{account_id}",
                    "target": f"community:{community_id}",
                }
            }
        )

    for row in _native_records(merchants):
        merchant_id = row["merchant_id"]
        nodes.append(
            {
                "data": {
                    "id": f"merchant:{merchant_id}",
                    "label": "MERCHANT",
                    "name": row["merchant_name"],
                    **row,
                }
            }
        )

    for row in _native_records(transfers):
        src = row["src_account_id"]
        dst = row["dst_account_id"]
        edges.append(
            {
                "data": {
                    "id": f"transfer:{src}:{dst}",
                    "label": "TRANSFERRED_TO",
                    "source": f"account:{src}",
                    "target": f"account:{dst}",
                    **row,
                }
            }
        )

    for row in _native_records(account_merchants):
        account_id = row["account_id"]
        merchant_id = row["merchant_id"]
        edges.append(
            {
                "data": {
                    "id": f"merchant:{account_id}:{merchant_id}",
                    "label": "TRANSACTED_WITH",
                    "source": f"account:{account_id}",
                    "target": f"merchant:{merchant_id}",
                    **row,
                }
            }
        )

    for row in _native_records(similarities):
        account_a = row["account_id_a"]
        account_b = row["account_id_b"]
        edges.append(
            {
                "data": {
                    "id": f"similarity:{account_a}:{account_b}",
                    "label": "SIMILAR_TO",
                    "source": f"account:{account_a}",
                    "target": f"account:{account_b}",
                    **row,
                }
            }
        )

    return {"nodes": nodes, "edges": edges}
