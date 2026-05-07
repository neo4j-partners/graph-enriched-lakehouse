"""Validate Databricks-side preconditions for the simple-finance-agnet agent."""

from __future__ import annotations

import json
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient

from _job_bootstrap import inject_params, setting

inject_params()


READINESS_QUERY = "RETURN 1 AS ok"


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
    connection_name = setting("UC_CONNECTION_NAME")

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
    result = _call_read_cypher(mcp_client, read_cypher_tool, READINESS_QUERY)
    print("OK    read-only Cypher readiness query executed through Neo4j MCP")
    print(str(result)[:3000])


if __name__ == "__main__":
    main()
