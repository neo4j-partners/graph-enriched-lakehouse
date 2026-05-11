# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "databricks-sdk>=0.40",
#     "python-dotenv>=1.0",
# ]
# ///
"""Preflight the Databricks cluster before any `cli submit` job.

Three checks:

  1. Cluster ID shape      DATABRICKS_CLUSTER_ID matches NNNN-NNNNNN-xxxxxxxx
                           (catches the common mistake of pasting a workspace
                           host prefix like `adb-<workspace-id>.<shard>`)
  2. Cluster state         cluster exists and is RUNNING
  3. Required libraries    graphdatascience (PyPI) and
                           org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
                           (Maven) are installed on the cluster

Reads DATABRICKS_CLUSTER_ID and DATABRICKS_PROFILE from ../.env.

Run from enrichment-pipeline/:

    uv run validation/validate_cluster.py

Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import os
import re
import sys

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound

from _common import fail, load_env, ok

CLUSTER_ID_RE = re.compile(r"^\d{4}-\d{6}-[a-z0-9]{8}$")

REQUIRED_PYPI = "graphdatascience"
# Match on artifact prefix only; the Scala version (_2.12 vs _2.13) and
# connector release (5.3.1, 5.3.10, …) depend on the cluster's Spark runtime
# and are chosen per-cluster. Hardcoding the full coordinate rejects valid
# installs for no benefit.
REQUIRED_MAVEN_PREFIX = "org.neo4j:neo4j-connector-apache-spark"


def check_id_shape(cluster_id: str) -> list[str]:
    if CLUSTER_ID_RE.match(cluster_id):
        ok(f"cluster ID shape: {cluster_id}")
        return []
    return [
        f"DATABRICKS_CLUSTER_ID={cluster_id!r} does not look like a cluster ID "
        f"(expected NNNN-NNNNNN-xxxxxxxx). A workspace host prefix like "
        f"`adb-…` will not work with `cli submit`"
    ]


def check_cluster_state(ws, cluster_id: str) -> list[str]:
    try:
        cluster = ws.clusters.get(cluster_id)
    except NotFound:
        return [
            f"cluster {cluster_id} does not exist in this workspace — "
            f"check DATABRICKS_CLUSTER_ID in .env"
        ]
    except Exception as e:
        return [f"cannot fetch cluster {cluster_id}: {e}"]

    state = str(getattr(cluster.state, "value", cluster.state))
    name = cluster.cluster_name or "(unnamed)"
    if state == "RUNNING":
        ok(f"cluster {cluster_id} ({name}) is RUNNING")
        return []
    return [
        f"cluster {cluster_id} ({name}) is {state}, not RUNNING. "
        f"Start it via the Databricks UI or `databricks clusters start {cluster_id}`"
    ]


def check_libraries(ws, cluster_id: str) -> list[str]:
    try:
        status = ws.libraries.cluster_status(cluster_id)
    except Exception as e:
        return [f"cannot fetch library status for {cluster_id}: {e}"]

    found_pypi: str | None = None
    found_maven: str | None = None
    installed_labels: list[str] = []

    for lib_full_status in status:
        lib = lib_full_status.library
        lib_state = str(getattr(lib_full_status.status, "value", lib_full_status.status))
        if lib.pypi and lib.pypi.package:
            pkg = lib.pypi.package.split("==")[0].split(">")[0].split("<")[0].strip()
            installed_labels.append(f"pypi:{pkg}({lib_state})")
            if pkg.lower() == REQUIRED_PYPI.lower() and lib_state == "INSTALLED":
                found_pypi = pkg
        elif lib.maven and lib.maven.coordinates:
            coord = lib.maven.coordinates
            installed_labels.append(f"maven:{coord}({lib_state})")
            if coord.startswith(REQUIRED_MAVEN_PREFIX) and lib_state == "INSTALLED":
                found_maven = coord

    problems: list[str] = []
    if found_pypi:
        ok(f"library installed: pypi:{found_pypi}")
    else:
        problems.append(f"required PyPI library not INSTALLED: {REQUIRED_PYPI}")

    if found_maven:
        ok(f"library installed: maven:{found_maven}")
    else:
        problems.append(
            f"required Maven library not INSTALLED: "
            f"{REQUIRED_MAVEN_PREFIX}_<scala>:<version>_for_spark_<n>"
        )

    if problems:
        print(f"      installed libraries on cluster: {installed_labels or '(none)'}")

    return problems


def main() -> None:
    load_env(("DATABRICKS_CLUSTER_ID",))
    cluster_id = os.environ["DATABRICKS_CLUSTER_ID"].strip()

    profile = os.environ.get("DATABRICKS_PROFILE", "").strip()
    if profile:
        os.environ["DATABRICKS_CONFIG_PROFILE"] = profile
        print(f"OK    using Databricks profile: {profile}")

    problems: list[str] = []

    problems += check_id_shape(cluster_id)
    if problems:
        # No point hitting the API with a clearly malformed ID.
        print()
        print(f"FAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    try:
        ws = WorkspaceClient()
    except Exception as e:
        fail(f"WorkspaceClient() failed: {e}")

    problems += check_cluster_state(ws, cluster_id)
    problems += check_libraries(ws, cluster_id)

    print()
    if problems:
        print(f"FAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("PASS  cluster is ready for `cli submit`.")


if __name__ == "__main__":
    main()
