"""
Data access layer for the Graph-Enriched Lakehouse Explorer.

All queries run against a Databricks SQL Warehouse via databricks-sql-connector.
Connection is cached with @st.cache_resource; query results with @st.cache_data.
"""

import os
import streamlit as st
import pandas as pd
from databricks.sdk.core import Config
from databricks import sql

CATALOG = os.getenv("CATALOG", "graph-enriched-lakehouse")
SCHEMA = os.getenv("SCHEMA", "graph-enriched-schema")


def _fqn(table: str) -> str:
    """Return fully qualified table name."""
    return f"`{CATALOG}`.`{SCHEMA}`.`{table}`"


@st.cache_resource(ttl=600)
def get_connection():
    """Create a cached SQL Warehouse connection."""
    cfg = Config()
    return sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _query(sql_text: str) -> pd.DataFrame:
    """Execute SQL and return a pandas DataFrame."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql_text)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ──────────────────────────────────────────────
# BEFORE ENRICHMENT QUERIES
# ──────────────────────────────────────────────


@st.cache_data(ttl=300)
def get_overview_stats() -> dict:
    """Basic dataset stats: total accounts, fraud accounts, total transactions, total P2P links."""
    df = _query(f"""
        SELECT
            (SELECT COUNT(*) FROM {_fqn('accounts')}) AS total_accounts,
            (SELECT COUNT(*) FROM {_fqn('account_labels')} WHERE is_fraud = true) AS fraud_accounts,
            (SELECT COUNT(*) FROM {_fqn('transactions')}) AS total_transactions,
            (SELECT COUNT(*) FROM {_fqn('account_links')}) AS total_p2p_links
    """)
    return df.iloc[0].to_dict()


@st.cache_data(ttl=300)
def get_top_accounts_by_inbound(top_n: int = 200) -> pd.DataFrame:
    """Top accounts ranked by inbound P2P transfer count, with fraud labels."""
    return _query(f"""
        SELECT
            a.account_id,
            a.account_type,
            a.region,
            COUNT(l.link_id) AS inbound_count,
            SUM(l.amount) AS inbound_total,
            COALESCE(lab.is_fraud, false) AS is_fraud
        FROM {_fqn('accounts')} a
        JOIN {_fqn('account_links')} l ON l.dst_account_id = a.account_id
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = a.account_id
        GROUP BY a.account_id, a.account_type, a.region, lab.is_fraud
        ORDER BY inbound_count DESC
        LIMIT {top_n}
    """)


@st.cache_data(ttl=300)
def get_bilateral_pairs(top_n: int = 50) -> pd.DataFrame:
    """Top account pairs by mutual transfer count."""
    return _query(f"""
        WITH directed AS (
            SELECT src_account_id, dst_account_id, COUNT(*) AS cnt
            FROM {_fqn('account_links')}
            GROUP BY src_account_id, dst_account_id
        )
        SELECT
            a.src_account_id AS account_a,
            a.dst_account_id AS account_b,
            a.cnt + COALESCE(b.cnt, 0) AS mutual_transfers,
            COALESCE(la.is_fraud, false) AS a_is_fraud,
            COALESCE(lb.is_fraud, false) AS b_is_fraud
        FROM directed a
        LEFT JOIN directed b
            ON a.src_account_id = b.dst_account_id
            AND a.dst_account_id = b.src_account_id
        LEFT JOIN {_fqn('account_labels')} la ON la.account_id = a.src_account_id
        LEFT JOIN {_fqn('account_labels')} lb ON lb.account_id = a.dst_account_id
        WHERE a.src_account_id < a.dst_account_id
        ORDER BY mutual_transfers DESC
        LIMIT {top_n}
    """)


@st.cache_data(ttl=300)
def get_avg_txn_amount_by_fraud() -> pd.DataFrame:
    """Average transaction amount per account, split by fraud label."""
    return _query(f"""
        SELECT
            t.account_id,
            AVG(t.amount) AS avg_amount,
            COUNT(*) AS txn_count,
            COALESCE(lab.is_fraud, false) AS is_fraud
        FROM {_fqn('transactions')} t
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = t.account_id
        GROUP BY t.account_id, lab.is_fraud
    """)


@st.cache_data(ttl=300)
def get_fraud_in_top_n_volume(top_n: int = 200) -> dict:
    """How many fraud accounts appear in the top-N by inbound volume."""
    df = get_top_accounts_by_inbound(top_n)
    fraud_count = int(df["is_fraud"].sum())
    return {
        "top_n": top_n,
        "fraud_in_top_n": fraud_count,
        "pct": round(100 * fraud_count / max(len(df), 1), 1),
    }


# ──────────────────────────────────────────────
# AFTER ENRICHMENT QUERIES
# ──────────────────────────────────────────────


@st.cache_data(ttl=300)
def get_gold_accounts() -> pd.DataFrame:
    """Full gold_accounts table with fraud labels."""
    return _query(f"""
        SELECT
            g.account_id,
            g.account_type,
            g.region,
            g.balance,
            g.holder_age,
            g.risk_score,
            g.community_id,
            g.similarity_score,
            COALESCE(lab.is_fraud, false) AS is_fraud
        FROM {_fqn('gold_accounts')} g
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = g.account_id
    """)


@st.cache_data(ttl=300)
def get_risk_score_summary() -> pd.DataFrame:
    """Average risk_score by fraud status."""
    return _query(f"""
        SELECT
            COALESCE(lab.is_fraud, false) AS is_fraud,
            AVG(g.risk_score) AS avg_risk_score,
            MIN(g.risk_score) AS min_risk_score,
            MAX(g.risk_score) AS max_risk_score,
            COUNT(*) AS account_count
        FROM {_fqn('gold_accounts')} g
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = g.account_id
        GROUP BY lab.is_fraud
    """)


@st.cache_data(ttl=300)
def get_community_stats() -> pd.DataFrame:
    """Per-community stats: size, fraud count, purity."""
    return _query(f"""
        SELECT
            g.community_id,
            COUNT(*) AS member_count,
            SUM(CASE WHEN lab.is_fraud THEN 1 ELSE 0 END) AS fraud_count,
            ROUND(100.0 * SUM(CASE WHEN lab.is_fraud THEN 1 ELSE 0 END) / COUNT(*), 1) AS purity_pct
        FROM {_fqn('gold_accounts')} g
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = g.account_id
        GROUP BY g.community_id
        ORDER BY fraud_count DESC
    """)


@st.cache_data(ttl=300)
def get_community_members(community_id: int) -> pd.DataFrame:
    """Members of a specific Louvain community."""
    return _query(f"""
        SELECT
            g.account_id,
            g.account_type,
            g.risk_score,
            g.similarity_score,
            COALESCE(lab.is_fraud, false) AS is_fraud
        FROM {_fqn('gold_accounts')} g
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = g.account_id
        WHERE g.community_id = {community_id}
        ORDER BY g.risk_score DESC
    """)


@st.cache_data(ttl=300)
def get_similarity_pairs(top_n: int = 100) -> pd.DataFrame:
    """Top similarity pairs with fraud labels."""
    return _query(f"""
        SELECT
            s.account_id_a,
            s.account_id_b,
            s.similarity_score,
            COALESCE(la.is_fraud, false) AS a_is_fraud,
            COALESCE(lb.is_fraud, false) AS b_is_fraud,
            CASE
                WHEN la.is_fraud AND lb.is_fraud THEN 'Both Fraud'
                WHEN la.is_fraud OR lb.is_fraud THEN 'Mixed'
                ELSE 'Both Normal'
            END AS pair_type
        FROM {_fqn('gold_account_similarity_pairs')} s
        LEFT JOIN {_fqn('account_labels')} la ON la.account_id = s.account_id_a
        LEFT JOIN {_fqn('account_labels')} lb ON lb.account_id = s.account_id_b
        ORDER BY s.similarity_score DESC
        LIMIT {top_n}
    """)


@st.cache_data(ttl=300)
def get_fraud_in_top_n_risk(top_n: int = 200) -> dict:
    """How many fraud accounts appear in the top-N by risk_score."""
    df = _query(f"""
        SELECT
            g.account_id,
            g.risk_score,
            COALESCE(lab.is_fraud, false) AS is_fraud
        FROM {_fqn('gold_accounts')} g
        LEFT JOIN {_fqn('account_labels')} lab ON lab.account_id = g.account_id
        ORDER BY g.risk_score DESC
        LIMIT {top_n}
    """)
    fraud_count = int(df["is_fraud"].sum())
    return {
        "top_n": top_n,
        "fraud_in_top_n": fraud_count,
        "pct": round(100 * fraud_count / max(len(df), 1), 1),
    }
