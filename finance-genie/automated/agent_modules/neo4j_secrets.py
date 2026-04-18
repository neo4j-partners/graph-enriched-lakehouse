"""Shared helper for agent modules that talk to Neo4j via the Spark Connector.

Resolves Neo4j credentials from a Databricks secret scope and returns them
together with the fully-formed `NEO4J_OPTS` dict that the Spark Connector
expects (`.options(**NEO4J_OPTS)`). Keeping the dict here means `batch.size`
and any future connector-option tuning lives in one place.

Usage (from an agent module running on the cluster):

    from neo4j_secrets import load_neo4j_opts
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_OPTS = load_neo4j_opts(SECRET_SCOPE)

Callers must have already put the agent_modules directory on sys.path; see
the sibling-import preamble in neo4j_ingest.py / pull_gold_tables.py.
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient


def load_neo4j_opts(secret_scope: str) -> tuple[str, str, str, dict[str, str]]:
    """Fetch (uri, user, password) from the scope and build NEO4J_OPTS."""
    ws = WorkspaceClient()
    uri = ws.dbutils.secrets.get(scope=secret_scope, key="uri")
    user = ws.dbutils.secrets.get(scope=secret_scope, key="username")
    password = ws.dbutils.secrets.get(scope=secret_scope, key="password")
    opts = {
        "url": uri,
        "authentication.basic.username": user,
        "authentication.basic.password": password,
        "batch.size": "10000",
    }
    return uri, user, password, opts
