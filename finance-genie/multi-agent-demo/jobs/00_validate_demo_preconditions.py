"""Validate Databricks-side preconditions for the Neo4j GDS specialist."""

from __future__ import annotations

import json
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks_mcp import DatabricksMCPClient

from _job_bootstrap import inject_params, setting

inject_params()


BASE_TABLES = (
    "accounts",
    "merchants",
    "transactions",
    "account_links",
)

GDS_READINESS_QUERY = """
MATCH (a:Account)
RETURN
  count(a) AS account_count,
  sum(CASE WHEN a.risk_score IS NULL THEN 0 ELSE 1 END) AS risk_score_count,
  sum(CASE WHEN a.community_id IS NULL THEN 0 ELSE 1 END) AS community_id_count,
  sum(CASE WHEN a.similarity_score IS NULL THEN 0 ELSE 1 END) AS similarity_score_count
"""


def _tool_names(tools: list[Any]) -> list[str]:
    return [str(getattr(tool, "name", "")) for tool in tools]


def _find_read_cypher_tool(tools: list[Any]) -> str:
    names = _tool_names(tools)
    for name in names:
        lowered = name.lower()
        if "read" in lowered and "cypher" in lowered:
            return name
    raise RuntimeError(
        "No read-Cypher MCP tool found. Discovered tools: "
        f"{json.dumps(names, indent=2)}"
    )


def _call_read_cypher(client: DatabricksMCPClient, tool_name: str, query: str) -> Any:
    try:
        return client.call_tool(tool_name, {"query": query})
    except Exception as exc:
        raise RuntimeError(
            f"Failed to call MCP read-Cypher tool {tool_name!r}. "
            "Confirm the Neo4j MCP server exposes a read-only Cypher tool "
            "with a query argument."
        ) from exc


def main() -> None:
    workspace = WorkspaceClient()
    catalog = setting("CATALOG")
    schema = setting("SCHEMA")
    connection_name = setting("UC_CONNECTION_NAME")

    for table_name in BASE_TABLES:
        full_name = f"{catalog}.{schema}.{table_name}"
        try:
            workspace.tables.get(full_name=full_name)
        except NotFound:
            raise RuntimeError(f"required base table not found: {full_name}") from None
        print(f"OK    base table exists: {full_name}")

    host = workspace.config.host.rstrip("/")
    server_url = f"{host}/api/2.0/mcp/external/{connection_name}"
    mcp_client = DatabricksMCPClient(
        server_url=server_url,
        workspace_client=workspace,
    )
    tools = mcp_client.list_tools()
    if not tools:
        raise RuntimeError(f"no tools discovered from Neo4j MCP server: {server_url}")

    names = _tool_names(tools)
    print(f"OK    Neo4j MCP tools discovered: {len(names)}")
    print(json.dumps(names, indent=2))

    read_cypher_tool = _find_read_cypher_tool(tools)
    gds_result = _call_read_cypher(mcp_client, read_cypher_tool, GDS_READINESS_QUERY)
    print("OK    GDS readiness query executed through Neo4j MCP")
    print(str(gds_result)[:3000])
    print()
    print(
        "Review the readiness result above. account_count should be positive and "
        "at least one GDS column count should be positive before running a live demo."
    )


if __name__ == "__main__":
    main()
