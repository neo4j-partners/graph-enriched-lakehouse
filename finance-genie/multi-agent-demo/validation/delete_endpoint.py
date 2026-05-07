"""Delete the graph-specialist serving endpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Databricks CLI profile to use")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm endpoint deletion without an interactive prompt.",
    )
    args = parser.parse_args()

    settings = load_settings()
    endpoint_name = settings.model_serving_endpoint_name
    if not args.yes:
        answer = input(f"Delete serving endpoint {endpoint_name!r}? Type 'delete': ")
        if answer != "delete":
            print("Aborted.")
            return 1

    workspace = (
        WorkspaceClient(profile=args.profile or settings.databricks_profile)
        if args.profile or settings.databricks_profile
        else WorkspaceClient()
    )
    try:
        workspace.serving_endpoints.delete(endpoint_name)
    except NotFound:
        print(f"Endpoint already absent: {endpoint_name}")
        return 0
    print(f"OK    deleted serving endpoint: {endpoint_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
