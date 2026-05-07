"""MCP-backed Neo4j graph schema view for the finance demo."""

from __future__ import annotations

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Live Neo4j Graph Schema", layout="wide")

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


def clear_mcp_cache() -> None:
    db.list_mcp_schema_tools.clear()
    db.call_mcp_tool.clear()
    db.call_mcp_schema_tool.clear()
    db.mcp_read_cypher.clear()
    db.neo4j_mcp_communities.clear()
    db.neo4j_mcp_sample_elements.clear()


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


def schema_node_styles() -> list:
    if NodeStyle is None:
        return []
    return [
        NodeStyle("ACCOUNT", "#0f766e", "name", "account_circle"),
        NodeStyle("MERCHANT", "#2563eb", "name", "storefront"),
        NodeStyle("RELATIONSHIP", "#475569", "name", "hub"),
    ]


def schema_edge_styles() -> list:
    if EdgeStyle is None:
        return []
    return [
        EdgeStyle("TRANSFERRED_TO", caption="label", directed=True),
        EdgeStyle("TRANSACTED_WITH", caption="label", directed=True),
        EdgeStyle("SIMILAR_TO", caption="label", directed=False),
    ]


def tool_display_name(tool: dict[str, object]) -> str:
    name = str(tool.get("name", ""))
    description = str(tool.get("description", "")).strip()
    return f"{name} - {description}" if description else name


def schema_graph_elements(
    tables: pd.DataFrame,
    relationships: pd.DataFrame,
) -> dict[str, list[dict[str, dict[str, object]]]]:
    nodes: dict[str, dict[str, object]] = {}
    edges: dict[str, dict[str, object]] = {}

    if not tables.empty:
        for row in tables.to_dict("records"):
            item_type = str(row.get("Type", "")).lower()
            table = str(row.get("Table", ""))
            if item_type == "node":
                nodes[table] = {
                    "id": table,
                    "label": table.upper(),
                    "name": table,
                    "properties": row.get("Column count", 0),
                }

    if not relationships.empty:
        for index, row in enumerate(relationships.to_dict("records")):
            source = str(row.get("Source", ""))
            relationship = str(row.get("Relationship", ""))
            targets = [
                item.strip()
                for item in str(row.get("Target labels", "")).split(",")
                if item.strip()
            ]
            if source and source not in nodes:
                nodes[source] = {"id": source, "label": source.upper(), "name": source}
            for target in targets:
                if target not in nodes:
                    nodes[target] = {"id": target, "label": target.upper(), "name": target}
                edge_id = f"{source}-{relationship}-{target}-{index}"
                edges[edge_id] = {
                    "id": edge_id,
                    "label": relationship,
                    "source": source,
                    "target": target,
                    "direction": row.get("Direction", ""),
                }

    return {
        "nodes": [{"data": item} for item in nodes.values()],
        "edges": [{"data": item} for item in edges.values()],
    }


inject_styles()

st.title("Live Neo4j Graph Schema")
st.markdown(
    """
    This page retrieves the graph sample and graph schema directly from Neo4j
    through the Databricks MCP proxy.
    """
)

connection_label = db.MCP_SCHEMA_CONNECTION_NAME or "Not configured"
left, middle, right = st.columns(3)
left.metric("MCP connection", connection_label)
middle.metric("Schema tool", db.MCP_SCHEMA_TOOL_NAME.split("___")[-1])
right.metric("Cypher tool", db.MCP_CYPHER_TOOL_NAME.split("___")[-1])

if not db.mcp_schema_is_configured():
    st.warning(
        "MCP schema retrieval is not configured. Set MCP_SCHEMA_CONNECTION_NAME "
        "to a Unity Catalog HTTP connection that points at the MCP server."
    )
    st.stop()

with st.sidebar:
    st.markdown("### MCP Graph")
    st.caption(f"Connection: {db.MCP_SCHEMA_CONNECTION_NAME}")
    st.caption(f"Schema args: {db.MCP_SCHEMA_TOOL_ARGUMENTS}")
    if st.button("Refresh MCP data", use_container_width=True):
        clear_mcp_cache()
        st.rerun()

try:
    tools = db.list_mcp_schema_tools()
except Exception as exc:  # noqa: BLE001
    st.error(f"Unable to list MCP tools: {exc}")
    st.stop()

sample_tab, schema_tab = st.tabs(["Sample Community", "Schema"])

with sample_tab:
    st.markdown(
        """
        <div class="fg-note">
          <strong>Neo4j MCP sample</strong>
          This graph is queried from Neo4j through Databricks MCP
          <code>read-cypher</code>. It shows accounts in a selected GDS community,
          their account-to-account relationships, and a bounded set of merchant
          transactions.
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        communities = db.neo4j_mcp_communities()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Neo4j MCP communities are unavailable: {exc}")
        communities = pd.DataFrame()

    if communities.empty:
        st.info("No Neo4j communities are available from the configured MCP server.")
    else:
        selected = st.selectbox(
            "Community",
            communities["community_id"].tolist(),
            format_func=lambda value: f"Community {value}",
        )
        account_limit = st.slider("Accounts", min_value=20, max_value=100, value=60, step=10)

        try:
            elements = db.neo4j_mcp_sample_elements(
                int(selected),
                account_limit=account_limit,
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Neo4j MCP graph sample is unavailable: {exc}")
        else:
            st.caption(
                "Graph source: Neo4j MCP `read-cypher` over Account, Merchant, "
                "TRANSFERRED_TO, TRANSACTED_WITH, and SIMILAR_TO records."
            )
            render_graph(elements, sample_node_styles(), sample_edge_styles())

        st.markdown("#### Neo4j communities")
        st.dataframe(communities, hide_index=True, use_container_width=True)

with schema_tab:
    st.markdown(
        """
        <div class="fg-note">
          <strong>MCP get-schema</strong>
          This schema is returned by the Neo4j MCP
          <code>get-schema</code> tool. Node labels, relationship types, and
          properties are normalized into graph and table views.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tool_names = [
        str(tool.get("name"))
        for tool in tools
        if isinstance(tool, dict) and tool.get("name")
    ]
    if tool_names:
        default_index = (
            tool_names.index(db.MCP_SCHEMA_TOOL_NAME)
            if db.MCP_SCHEMA_TOOL_NAME in tool_names
            else 0
        )
        selected_tool = st.selectbox(
            "Schema tool",
            tool_names,
            index=default_index,
            format_func=lambda name: next(
                (
                    tool_display_name(tool)
                    for tool in tools
                    if isinstance(tool, dict) and tool.get("name") == name
                ),
                name,
            ),
        )
    else:
        selected_tool = st.text_input("Schema tool", value=db.MCP_SCHEMA_TOOL_NAME)

    try:
        raw_response = db.call_mcp_schema_tool(
            tool_name=selected_tool,
            catalog=db.CATALOG,
            schema=db.SCHEMA,
            argument_mode=db.MCP_SCHEMA_TOOL_ARGUMENTS,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to retrieve schema through MCP: {exc}")
        st.stop()

    normalized = db.normalize_mcp_schema_response(raw_response)
    tables = normalized["tables"]
    columns = normalized["columns"]
    relationships = normalized["relationships"]

    metric_left, metric_middle, metric_right = st.columns(3)
    metric_left.metric("Schema entities", len(tables))
    metric_middle.metric("Properties", len(columns))
    metric_right.metric("Relationships", len(relationships))

    render_graph(
        schema_graph_elements(tables, relationships),
        schema_node_styles(),
        schema_edge_styles(),
        layout="circle",
    )

    tables_tab, columns_tab, relationships_tab, raw_tab = st.tabs(
        ["Entities", "Properties", "Relationships", "Raw MCP Response"]
    )

    with tables_tab:
        st.dataframe(tables, hide_index=True, use_container_width=True)
    with columns_tab:
        st.dataframe(columns, hide_index=True, use_container_width=True)
    with relationships_tab:
        st.dataframe(relationships, hide_index=True, use_container_width=True)
    with raw_tab:
        with st.expander("Available MCP tools", expanded=False):
            st.json(tools)
        st.json(raw_response)
