"""Smoke test the deployed Neo4j GDS fraud specialist endpoint."""

from __future__ import annotations

import json

from databricks.sdk import WorkspaceClient

from _job_bootstrap import inject_params, setting

inject_params()


def contains_tool_output(value: object) -> bool:
    if isinstance(value, dict):
        item_type = str(value.get("type", "")).lower()
        if "tool" in item_type:
            return True
        if value.get("tool_call_id") or value.get("tool_name"):
            return True
        return any(contains_tool_output(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_tool_output(item) for item in value)
    return False


def contains_graph_candidate_language(value: object) -> bool:
    text = json.dumps(value, default=str).lower()
    markers = (
        "candidate",
        "account",
        "community",
        "risk",
        "similar",
        "gds",
        "genie",
    )
    return any(marker in text for marker in markers)


def main() -> None:
    workspace = WorkspaceClient()
    endpoint_name = setting(
        "MODEL_SERVING_ENDPOINT_NAME", "finance-neo4j-gds-fraud-specialist"
    )
    prompt = setting(
        "SMOKE_TEST_PROMPT",
        (
            "Find likely fraud-ring candidates from Neo4j GDS results. Return "
            "compact account IDs, graph evidence, and a recommended BEFORE "
            "Genie follow-up prompt for silver-table analysis."
        ),
    )
    response = workspace.serving_endpoints.query(
        name=endpoint_name,
        inputs={"input": [{"role": "user", "content": prompt}]},
    )
    payload = response.as_dict()
    print(json.dumps(payload, indent=2)[:5000])
    if not contains_tool_output(payload):
        raise RuntimeError("endpoint response did not contain a tool call result")
    if not contains_graph_candidate_language(payload):
        raise RuntimeError(
            "endpoint response did not include expected graph-candidate language"
        )
    print("OK    endpoint response contained a graph tool result")


if __name__ == "__main__":
    main()
