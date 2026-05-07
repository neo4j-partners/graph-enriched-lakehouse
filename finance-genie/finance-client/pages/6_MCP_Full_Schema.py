"""MCP-backed full schema view for the finance demo."""

from __future__ import annotations

import streamlit as st


st.set_page_config(page_title="MCP Full Schema", layout="wide")

import backend as db


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
    db.call_mcp_schema_tool.clear()


def tool_display_name(tool: dict[str, object]) -> str:
    name = str(tool.get("name", ""))
    description = str(tool.get("description", "")).strip()
    return f"{name} - {description}" if description else name


inject_styles()

st.title("MCP Full Schema")
st.markdown(
    """
    This page retrieves the configured lakehouse schema through a Databricks MCP
    server and renders the response as tables, columns, relationships, and raw
    JSON.
    """
)

connection_label = db.MCP_SCHEMA_CONNECTION_NAME or "Not configured"
left, middle, right = st.columns(3)
left.metric("Catalog", db.CATALOG)
middle.metric("Schema", db.SCHEMA)
right.metric("MCP connection", connection_label)

if not db.mcp_schema_is_configured():
    st.warning(
        "MCP schema retrieval is not configured. Set MCP_SCHEMA_CONNECTION_NAME "
        "to a Unity Catalog HTTP connection that points at the MCP server."
    )
    st.stop()

with st.sidebar:
    st.markdown("### MCP Schema")
    st.caption(f"Connection: {db.MCP_SCHEMA_CONNECTION_NAME}")
    st.caption(f"Path: {db.MCP_SCHEMA_PATH}")
    if st.button("Refresh schema", use_container_width=True):
        clear_mcp_cache()
        st.rerun()

try:
    tools = db.list_mcp_schema_tools()
except Exception as exc:  # noqa: BLE001
    st.error(f"Unable to list MCP tools: {exc}")
    st.stop()

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

with st.expander("Available MCP tools", expanded=False):
    if tools:
        st.json(tools)
    else:
        st.info("The MCP server did not return any tools.")

if not selected_tool:
    st.info("Select or enter an MCP schema tool.")
    st.stop()

with st.spinner("Retrieving schema from MCP server..."):
    try:
        raw_response = db.call_mcp_schema_tool(
            tool_name=selected_tool,
            catalog=db.CATALOG,
            schema=db.SCHEMA,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to retrieve schema through MCP: {exc}")
        st.stop()

normalized = db.normalize_mcp_schema_response(raw_response)
tables = normalized["tables"]
columns = normalized["columns"]
relationships = normalized["relationships"]

metric_left, metric_middle, metric_right = st.columns(3)
metric_left.metric("Tables", len(tables))
metric_middle.metric("Columns", len(columns))
metric_right.metric("Relationships", len(relationships))

tables_tab, columns_tab, relationships_tab, raw_tab = st.tabs(
    ["Tables", "Columns", "Relationships", "Raw MCP Response"]
)

with tables_tab:
    if tables.empty:
        st.info("No table records were recognized in the MCP schema response.")
    else:
        st.dataframe(tables, hide_index=True, use_container_width=True)

with columns_tab:
    if columns.empty:
        st.info("No column records were recognized in the MCP schema response.")
    else:
        table_filter = st.multiselect(
            "Table",
            sorted(columns["Table"].dropna().astype(str).unique().tolist()),
        )
        filtered_columns = (
            columns[columns["Table"].astype(str).isin(table_filter)]
            if table_filter
            else columns
        )
        st.dataframe(filtered_columns, hide_index=True, use_container_width=True)

with relationships_tab:
    if relationships.empty:
        st.info("No relationship records were recognized in the MCP schema response.")
    else:
        st.dataframe(relationships, hide_index=True, use_container_width=True)

with raw_tab:
    st.json(raw_response)
