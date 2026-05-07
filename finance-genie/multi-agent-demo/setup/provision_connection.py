"""Create or validate the Unity Catalog HTTP connection used for Neo4j MCP."""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import NoReturn

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.compute import Language
from databricks.sdk.service.sql import StatementState

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Settings, load_settings  # noqa: E402

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
EXPECTED_OPTIONS = {
    "base_path": "/mcp",
    "is_mcp_connection": "true",
}
REDACTED_SECRET_OPTIONS = {"client_secret"}


def fail(message: str) -> NoReturn:
    print(f"FAIL  {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK    {message}")


def validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_RE.match(value):
        fail(
            f"{label}={value!r} is not a simple Databricks identifier. "
            "Use letters, numbers, and underscores, starting with a letter "
            "or underscore."
        )


def workspace_client(settings: Settings, profile: str | None) -> WorkspaceClient:
    selected_profile = profile or settings.databricks_profile
    if selected_profile:
        ok(f"using Databricks profile: {selected_profile}")
        return WorkspaceClient(profile=selected_profile)
    return WorkspaceClient()


def execute_sql(settings: Settings, workspace: WorkspaceClient, sql: str) -> None:
    if settings.databricks_warehouse_id:
        response = workspace.statement_execution.execute_statement(
            statement=sql,
            warehouse_id=settings.databricks_warehouse_id,
            wait_timeout="50s",
        )
        statement_id = response.statement_id
        state = response.status.state if response.status else None
        while state in {StatementState.PENDING, StatementState.RUNNING}:
            if not statement_id:
                fail("SQL statement did not return a statement_id for polling")
            time.sleep(2)
            response = workspace.statement_execution.get_statement(statement_id)
            state = response.status.state if response.status else None
        if state != StatementState.SUCCEEDED:
            message = (
                response.status.error.message
                if response.status and response.status.error
                else response
            )
            fail(f"SQL statement failed: {message}")
        return

    if not settings.databricks_cluster_id:
        fail("set DATABRICKS_WAREHOUSE_ID or DATABRICKS_CLUSTER_ID in .env")

    context = workspace.command_execution.create(
        cluster_id=settings.databricks_cluster_id,
        language=Language.SQL,
    ).result()
    if not context.id:
        fail("Databricks command execution did not return a context id")
    try:
        result = workspace.command_execution.execute(
            cluster_id=settings.databricks_cluster_id,
            context_id=context.id,
            language=Language.SQL,
            command=sql,
        ).result()
        status = str(getattr(result.status, "value", result.status))
        if status != "Finished":
            fail(f"cluster SQL command failed with status {status}: {result.results}")
    finally:
        workspace.command_execution.destroy(settings.databricks_cluster_id, context.id)


def get_connection(workspace: WorkspaceClient, name: str):
    try:
        return workspace.connections.get(name)
    except NotFound:
        return None


def connection_type_name(connection) -> str | None:
    value = getattr(connection, "connection_type", None)
    return getattr(value, "value", value)


def connection_options(connection) -> dict[str, str]:
    return dict(getattr(connection, "options", None) or {})


def has_mcp_flag(connection) -> bool:
    options = {
        key.lower(): str(value).lower()
        for key, value in connection_options(connection).items()
    }
    properties = {
        key.lower(): str(value).lower()
        for key, value in (getattr(connection, "properties", None) or {}).items()
    }
    return (
        options.get("is_mcp_connection") == "true"
        or properties.get("is_mcp_connection") == "true"
    )


def connection_drift(connection) -> list[str]:
    problems: list[str] = []
    if connection_type_name(connection) != "HTTP":
        problems.append(
            f"connection type is {connection_type_name(connection)!r}, expected HTTP"
        )
    options = {key.lower(): str(value) for key, value in connection_options(connection).items()}
    for key, expected in EXPECTED_OPTIONS.items():
        actual = options.get(key)
        if actual is not None and actual.lower() != expected:
            problems.append(f"option {key} is {actual!r}, expected {expected!r}")
    for required in (
        "host",
        "base_path",
        "client_id",
        "oauth_scope",
        "token_endpoint",
    ):
        if required not in options:
            problems.append(f"connection option {required!r} is not visible")
    for redacted in REDACTED_SECRET_OPTIONS:
        actual = options.get(redacted)
        if actual is not None and actual.strip() == "":
            problems.append(f"connection option {redacted!r} is empty")
    if not has_mcp_flag(connection):
        problems.append("is_mcp_connection flag is not true")
    return problems


def create_connection_sql(connection_name: str, secret_scope: str) -> str:
    return f"""
CREATE CONNECTION IF NOT EXISTS {connection_name} TYPE HTTP
OPTIONS (
  host secret('{secret_scope}', 'gateway_host'),
  base_path '/mcp',
  client_id secret('{secret_scope}', 'client_id'),
  client_secret secret('{secret_scope}', 'client_secret'),
  oauth_scope secret('{secret_scope}', 'oauth_scope'),
  token_endpoint secret('{secret_scope}', 'token_endpoint'),
  is_mcp_connection 'true'
)
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Databricks CLI profile to use")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate the connection if it already exists or drifts.",
    )
    args = parser.parse_args()

    settings = load_settings()
    workspace = workspace_client(settings, args.profile)
    validate_identifier(settings.uc_connection_name, "UC_CONNECTION_NAME")

    existing = get_connection(workspace, settings.uc_connection_name)
    if existing and args.replace:
        execute_sql(
            settings,
            workspace,
            f"DROP CONNECTION IF EXISTS {settings.uc_connection_name}",
        )
        ok(f"dropped existing connection: {settings.uc_connection_name}")
        existing = None

    if existing:
        drift = connection_drift(existing)
        if drift:
            fail(
                "existing connection drift detected; rerun with --replace:\n"
                + "\n".join(f"  - {item}" for item in drift)
            )
        ok(f"connection already correct: {settings.uc_connection_name}")
    else:
        execute_sql(
            settings,
            workspace,
            create_connection_sql(
                settings.uc_connection_name,
                settings.mcp_secret_scope,
            ),
        )
        ok(f"created connection: {settings.uc_connection_name}")

    after = get_connection(workspace, settings.uc_connection_name)
    if not after:
        fail(f"connection was not found after create: {settings.uc_connection_name}")
    drift = connection_drift(after)
    if drift:
        fail(
            "connection exists but did not validate:\n"
            + "\n".join(f"  - {item}" for item in drift)
        )
    ok("connection validated with MCP flag enabled")


if __name__ == "__main__":
    main()
