#!/usr/bin/env python3
"""Upload the Finance Genie dbxcarta question set to the configured UC Volume."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from dotenv import load_dotenv


DEFAULT_SOURCE = Path(__file__).resolve().with_name("questions.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload sql-semantics/src/sql_semantics/questions.json to "
            "DBXCARTA_CLIENT_QUESTIONS."
        )
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the dbxcarta env file to load. Defaults to .env.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Local questions JSON file. Defaults to this package's questions.json.",
    )
    parser.add_argument(
        "--dest",
        default="",
        help=(
            "Override destination UC Volume path. Defaults to "
            "DBXCARTA_CLIENT_QUESTIONS from the env file."
        ),
    )
    return parser.parse_args()


def validate_source(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"question source file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise ValueError(f"question source must be a non-empty JSON array: {path}")


def validate_dest(dest: str) -> str:
    normalized = dest.rstrip("/")
    if not normalized:
        raise ValueError(
            "DBXCARTA_CLIENT_QUESTIONS is not set. Add the Finance Genie preset "
            "values to .env or pass --dest."
        )
    if not normalized.startswith("/Volumes/"):
        raise ValueError(
            "destination must be a Unity Catalog Volume path beginning with "
            f"/Volumes/: {normalized}"
        )
    if not normalized.endswith(".json"):
        raise ValueError(f"destination must be a JSON file path: {normalized}")
    return normalized


def create_parent(ws: WorkspaceClient, dest: str) -> None:
    parent = dest.rsplit("/", 1)[0]
    try:
        ws.files.create_directory(parent)
    except ResourceAlreadyExists:
        pass


def main() -> None:
    args = parse_args()
    load_dotenv(args.env_file)

    source = args.source
    dest = validate_dest(args.dest or os.environ.get("DBXCARTA_CLIENT_QUESTIONS", ""))
    validate_source(source)

    profile = os.environ.get("DATABRICKS_PROFILE") or None
    ws = WorkspaceClient(profile=profile)
    create_parent(ws, dest)

    with source.open("rb") as fh:
        ws.files.upload(file_path=dest, contents=fh, overwrite=True)

    print(f"uploaded {source} -> {dest}")


if __name__ == "__main__":
    main()
