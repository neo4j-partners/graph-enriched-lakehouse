"""Query the deployed graph-specialist serving endpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings  # noqa: E402


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
    prompt = args.prompt or settings.smoke_test_prompt
    response = workspace.serving_endpoints.query(
        name=settings.model_serving_endpoint_name,
        inputs={"input": [{"role": "user", "content": prompt}]},
    )
    print(json.dumps(response.as_dict(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
