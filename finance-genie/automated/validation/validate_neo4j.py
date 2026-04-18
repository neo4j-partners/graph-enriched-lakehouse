# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "neo4j>=5.20",
#     "python-dotenv>=1.0",
# ]
# ///
"""Validate that .env contains working Neo4j Aura credentials.

Run from this directory:

    uv run validate_neo4j.py

Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

REQUIRED_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL  {msg}")
    sys.exit(1)


def main() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.is_file():
        fail(f".env not found at {env_path}")

    load_dotenv(env_path, override=True)

    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        fail(f"missing or empty in .env: {', '.join(missing)}")

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]

    print(f"OK    .env loaded from {env_path}")
    print(f"OK    NEO4J_URI      = {uri}")
    print(f"OK    NEO4J_USERNAME = {user}")
    print(f"OK    NEO4J_PASSWORD = <{len(password)} chars>")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as e:
        fail(f"driver construction failed: {e}")

    try:
        driver.verify_connectivity()
        print("OK    verify_connectivity() succeeded")

        with driver.session() as session:
            record = session.run("RETURN 1 AS ok").single()
            if not record or record["ok"] != 1:
                fail("test query did not return 1")
            print("OK    test query RETURN 1 returned 1")

            info = session.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN name, versions[0] AS version, edition"
            ).single()
            if info:
                print(
                    f"OK    server: {info['name']} "
                    f"{info['version']} ({info['edition']})"
                )
    except AuthError as e:
        fail(f"authentication failed — check NEO4J_USERNAME / NEO4J_PASSWORD: {e}")
    except ServiceUnavailable as e:
        fail(f"cannot reach server — check NEO4J_URI / network: {e}")
    except Exception as e:
        fail(f"unexpected error: {e}")
    finally:
        try:
            driver.close()
        except Exception:
            pass

    print("\nPASS  Neo4j credentials in .env are valid and working.")


if __name__ == "__main__":
    main()
