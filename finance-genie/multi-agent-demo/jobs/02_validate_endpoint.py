"""Smoke test the deployed simple-finance-agnet agent endpoint."""

from __future__ import annotations

import json

from databricks.sdk import WorkspaceClient

from _job_bootstrap import inject_params, setting

inject_params()

DEFAULT_SMOKE_TEST_PROMPT = """
Use the Neo4j MCP read-only Cypher tool with exactly this query:

RETURN 1 AS ok

Return the result and mention that the MCP tool call succeeded.
"""


def contains_tool_output(value: object) -> bool:
    if isinstance(value, dict):
        item_type = str(value.get("type", "")).lower()
        if "tool" in item_type or item_type in {"function_call", "function_call_output"}:
            return True
        if value.get("tool_call_id") or value.get("tool_name") or value.get("call_id"):
            return True
        return any(contains_tool_output(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_tool_output(item) for item in value)
    return False


def contains_graph_candidate_language(value: object) -> bool:
    text = json.dumps(value, default=str).lower()
    markers = (
        "ok",
        "succeeded",
        "success",
        "mcp",
        "tool",
    )
    return any(marker in text for marker in markers)


def main() -> None:
    workspace = WorkspaceClient()
    endpoint_name = setting(
        "MODEL_SERVING_ENDPOINT_NAME", "simple-finance-agnet"
    )
    prompt = setting("SMOKE_TEST_PROMPT", DEFAULT_SMOKE_TEST_PROMPT)
    payload = workspace.api_client.do(
        "POST",
        f"/serving-endpoints/{endpoint_name}/invocations",
        body={"input": [{"role": "user", "content": prompt}]},
    )
    print(json.dumps(payload, indent=2)[:5000])
    if not contains_tool_output(payload):
        raise RuntimeError("endpoint response did not contain a tool call result")
    if not contains_graph_candidate_language(payload):
        raise RuntimeError(
            "endpoint response did not include expected MCP success language"
        )
    print("OK    endpoint response contained an MCP tool result")


if __name__ == "__main__":
    main()
