"""Graph schema view for the graph-enriched finance demo."""

from __future__ import annotations

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Lakehouse Graph Schema", layout="wide")

import backend as db

try:
    from st_link_analysis import EdgeStyle, NodeStyle, st_link_analysis
except ImportError:  # pragma: no cover - exercised in local envs without extras.
    EdgeStyle = None
    NodeStyle = None
    st_link_analysis = None


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1220px;
        }
        .fg-note {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            background: #f6f8fb;
            color: #162033;
            margin: 0.75rem 0 1rem;
        }
        .fg-note strong {
            display: block;
            margin-bottom: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def element_frames(elements: dict[str, list[dict[str, dict[str, object]]]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = pd.DataFrame([item["data"] for item in elements["nodes"]])
    edges = pd.DataFrame([item["data"] for item in elements["edges"]])
    return nodes, edges


def render_graph(
    elements: dict[str, list[dict[str, dict[str, object]]]],
    node_styles: list,
    edge_styles: list,
    layout: str = "cose",
) -> None:
    if not elements["nodes"]:
        st.info("No graph elements are available for this selection.")
        return

    if st_link_analysis is None:
        st.info(
            "`st-link-analysis` is not installed in this environment, so the "
            "graph is shown as node and edge tables."
        )
        nodes, edges = element_frames(elements)
        left, right = st.columns(2)
        with left:
            st.markdown("**Nodes**")
            st.dataframe(nodes, hide_index=True, use_container_width=True)
        with right:
            st.markdown("**Edges**")
            st.dataframe(edges, hide_index=True, use_container_width=True)
        return

    st_link_analysis(elements, layout, node_styles, edge_styles)


def schema_node_styles() -> list:
    if NodeStyle is None:
        return []
    return [
        NodeStyle("ACCOUNT", "#0f766e", "name", "account_circle"),
        NodeStyle("MERCHANT", "#2563eb", "name", "storefront"),
        NodeStyle("COMMUNITY", "#b45309", "name", "hub"),
        NodeStyle("ALGORITHM", "#6d28d9", "name", "settings"),
        NodeStyle("FEATURE", "#be123c", "name", "analytics"),
        NodeStyle("TABLE", "#475569", "name", "table_chart"),
    ]


def schema_edge_styles() -> list:
    if EdgeStyle is None:
        return []
    return [
        EdgeStyle("TRANSFERRED_TO", caption="label", directed=True),
        EdgeStyle("TRANSACTED_WITH", caption="label", directed=True),
        EdgeStyle("IN_COMMUNITY", caption="label", directed=True),
        EdgeStyle("SIMILAR_TO", caption="label", directed=False),
        EdgeStyle("ADDS", caption="label", directed=True),
        EdgeStyle("DERIVES", caption="label", directed=True),
        EdgeStyle("WRITES", caption="label", directed=True),
    ]


def sample_node_styles() -> list:
    if NodeStyle is None:
        return []
    return [
        NodeStyle("ACCOUNT", "#0f766e", "name", "account_circle"),
        NodeStyle("MERCHANT", "#2563eb", "name", "storefront"),
        NodeStyle("COMMUNITY", "#b45309", "name", "hub"),
    ]


def sample_edge_styles() -> list:
    if EdgeStyle is None:
        return []
    return [
        EdgeStyle("TRANSFERRED_TO", caption="label", directed=True),
        EdgeStyle("TRANSACTED_WITH", caption="label", directed=True),
        EdgeStyle("IN_COMMUNITY", caption="label", directed=True),
        EdgeStyle("SIMILAR_TO", caption="label", directed=False),
    ]


inject_styles()

st.title("Lakehouse Graph Schema")
st.markdown(
    """
    The graph schema makes the enrichment boundary visible: Silver tables define
    account, merchant, transfer, and transaction relationships; Neo4j GDS
    computes structural features; Databricks Gold Delta tables materialize those
    features for Genie and SQL Warehouse queries.
    """
)

sample_tab, schema_tab, enrichment_tab = st.tabs(
    ["Sample Community", "Schema", "GDS Enrichment"]
)

with sample_tab:
    st.markdown(
        """
        <div class="fg-note">
          <strong>Databricks SQL Warehouse sample</strong>
          This graph is queried from Databricks Delta tables through the app's
          SQL Warehouse connection. Neo4j GDS produced the features upstream;
          this page visualizes the materialized Gold results that Genie can
          query.
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        communities = db.ring_candidate_communities()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Ring-candidate communities are unavailable: {exc}")
        communities = pd.DataFrame()

    if communities.empty:
        st.info("No ring-candidate communities are available from the current catalog.")
    else:
        st.caption(
            "Source: Databricks SQL Warehouse over "
            f"{db.fqn('gold_fraud_ring_communities')}"
        )

        selected = st.selectbox(
            "Community",
            communities["community_id"].tolist(),
            format_func=lambda value: f"Community {value}",
        )
        account_limit = st.slider("Accounts", min_value=20, max_value=100, value=60, step=10)

        try:
            elements = db.graph_sample_elements(int(selected), account_limit=account_limit)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Graph sample is unavailable: {exc}")
        else:
            st.caption(
                "Graph source: Databricks SQL Warehouse queries over Gold Delta "
                "tables and Silver relationship tables."
            )
            render_graph(elements, sample_node_styles(), sample_edge_styles())

        st.markdown("#### Ring-candidate communities")
        st.dataframe(communities, hide_index=True, use_container_width=True)

with schema_tab:
    st.markdown(
        """
        <div class="fg-note">
          <strong>What this diagram shows</strong>
          Accounts and merchants are source entities. Communities, similarity
          pairs, and risk features are the additional graph-derived structures
          exposed after enrichment.
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_graph(db.graph_schema_elements(), schema_node_styles(), schema_edge_styles())
    st.markdown("### Table Mapping")
    st.dataframe(db.graph_schema_tables(), hide_index=True, use_container_width=True)

with enrichment_tab:
    st.markdown(
        """
        <div class="fg-note">
          <strong>What GDS adds</strong>
          GDS does not change the analyst workflow. It adds structural features,
          similarity edges, and community rollups that Genie can query as
          governed Gold data through Databricks SQL Warehouse.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(db.gds_enrichment_columns(), hide_index=True, use_container_width=True)

    left, middle, right = st.columns(3)
    with left:
        st.subheader("PageRank")
        st.metric("Gold field", "risk_score")
        st.caption("Centrality over the account transfer network.")
    with middle:
        st.subheader("Louvain")
        st.metric("Gold field", "community_id")
        st.caption("Dense transfer community assignment and rollups.")
    with right:
        st.subheader("Node Similarity")
        st.metric("Gold field", "similarity_score")
        st.caption("Shared-merchant overlap for account pairs.")
