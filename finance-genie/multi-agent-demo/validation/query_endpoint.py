"""Query the deployed simple-finance-agnet agent serving endpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings  # noqa: E402

DEFAULT_QUERY_PROMPT = """
Use the Neo4j MCP read-only Cypher tool with exactly this query:

RETURN 1 AS ok

Return the result and mention that the MCP tool call succeeded.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Databricks CLI profile to use")
    parser.add_argument("--prompt", help="Prompt to send to the endpoint")
    args = parser.parse_args()

    settings = load_settings()
    workspace = (
        WorkspaceClient(profile=args.profile or settings.databricks_profile)
        if args.profile or settings.databricks_profile
        else WorkspaceClient()
    )
    prompt = args.prompt or settings.smoke_test_prompt or DEFAULT_QUERY_PROMPT
    response = workspace.api_client.do(
        "POST",
        f"/serving-endpoints/{settings.model_serving_endpoint_name}/invocations",
        body={"input": [{"role": "user", "content": prompt}]},
    )
    print(json.dumps(response, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
