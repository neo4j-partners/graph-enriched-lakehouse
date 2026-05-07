"""Check whether the deployed graph-specialist serving endpoint is READY."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings  # noqa: E402


def _value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _ready(endpoint) -> bool:
    state = getattr(endpoint, "state", None)
    ready = _value(getattr(state, "ready", "")).upper()
    config_update = _value(getattr(state, "config_update", "")).upper()
    return ready == "READY" and config_update in {"", "NOT_UPDATING"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Databricks CLI profile to use")
    args = parser.parse_args()

    settings = load_settings()
    workspace = (
        WorkspaceClient(profile=args.profile or settings.databricks_profile)
        if args.profile or settings.databricks_profile
        else WorkspaceClient()
    )

    try:
        endpoint = workspace.serving_endpoints.get(
            settings.model_serving_endpoint_name
        )
    except NotFound:
        print(f"Endpoint not found: {settings.model_serving_endpoint_name}")
        return 1

    payload = endpoint.as_dict()
    print(json.dumps(payload.get("state", payload), indent=2, default=str))
    if not _ready(endpoint):
        return 1

    print(f"OK    endpoint READY: {settings.model_serving_endpoint_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
