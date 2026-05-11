#!/usr/bin/env -S uv run python
# /// script
# requires-python = ">=3.11"
# ///
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

APP_RUNTIME_PREFIX = "AGENTIC_COMMERCE_"
DEFAULT_APP_NAME = "agentic-commerce"
DEFAULT_APP_RESOURCE_KEY = "agentic-commerce-app"
DEFAULT_TARGET = "dev"
DEFAULT_RETAIL_AGENT_ENDPOINT_NAME = "agents_retail_assistant-retail-retail_agent_v3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy the demo client Databricks App from a .env file."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the environment file, relative to demo-client by default.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse the current .build directory instead of running apx build.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands and generated runtime env without running deploy.",
    )
    return parser.parse_args()


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Environment file not found: {path}")

    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            raise ValueError(f"Invalid .env line {line_number}: {raw_line!r}")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid empty .env key on line {line_number}")

        if value and value[0] in {"'", '"'}:
            parsed = shlex.split(value, comments=False, posix=True)
            value = parsed[0] if parsed else ""
        else:
            value = value.split(" #", 1)[0].strip()
        values[key] = value

    return values


def env_flag(values: dict[str, str], key: str, default: bool = False) -> bool:
    value = values.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def command_with_profile(
    base: list[str],
    *,
    profile: str | None,
    target: str,
    bundle_vars: dict[str, str] | None = None,
) -> list[str]:
    command = [*base, "--target", target]
    for key, value in sorted((bundle_vars or {}).items()):
        command.extend(["--var", f"{key}={value}"])
    if profile:
        command.extend(["--profile", profile])
    return command


def run(command: list[str], *, cwd: Path, env: dict[str, str], dry_run: bool) -> None:
    print(f"+ {shlex.join(command)}", flush=True)
    if dry_run:
        return
    subprocess.run(command, cwd=cwd, env=env, check=True)


def run_json(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    dry_run: bool,
) -> dict[str, Any] | None:
    print(f"+ {shlex.join(command)}", flush=True)
    if dry_run:
        return None

    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object from command: {shlex.join(command)}")
    return parsed


def yaml_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def remove_top_level_env_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False

    for line in lines:
        stripped = line.strip()
        is_top_level = bool(stripped) and line[:1] not in {" ", "\t", "\n", "\r"}
        if not skipping and line.startswith("env:"):
            skipping = True
            continue
        if skipping and not is_top_level:
            continue
        if skipping and is_top_level:
            skipping = False
        output.append(line)

    return "".join(output).rstrip() + "\n"


def write_runtime_env(app_yml: Path, runtime_env: dict[str, str]) -> None:
    if not app_yml.exists():
        raise FileNotFoundError(f"App config not found: {app_yml}")

    app_config = remove_top_level_env_block(app_yml.read_text())
    if runtime_env:
        app_config += "\nenv:\n"
        for key in sorted(runtime_env):
            app_config += f"  - name: {key}\n"
            app_config += f"    value: {yaml_quote(runtime_env[key])}\n"

    app_yml.write_text(app_config)


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = project_dir / env_file

    values = parse_env_file(env_file)
    process_env = os.environ.copy()
    process_env.update(values)
    ignored_cluster_id = process_env.pop("DATABRICKS_CLUSTER_ID", None)

    profile = values.get("DATABRICKS_PROFILE") or None
    target = values.get("DATABRICKS_BUNDLE_TARGET", DEFAULT_TARGET)
    app_name = values.get("DATABRICKS_APP_NAME", DEFAULT_APP_NAME)
    app_resource_key = values.get(
        "DATABRICKS_APP_RESOURCE_KEY", DEFAULT_APP_RESOURCE_KEY
    )
    strict_validate = env_flag(values, "DATABRICKS_DEPLOY_STRICT_VALIDATE")
    retail_agent_endpoint_name = (
        values.get("AGENTIC_COMMERCE_RETAIL_AGENT_ENDPOINT_NAME")
        or DEFAULT_RETAIL_AGENT_ENDPOINT_NAME
    )
    bundle_vars = {"retail_agent_endpoint_name": retail_agent_endpoint_name}
    runtime_env = {
        key: value
        for key, value in values.items()
        if key.startswith(APP_RUNTIME_PREFIX) and value != ""
    }

    print(f"Using env file: {env_file}")
    print(f"Bundle target: {target}")
    print(f"Databricks app: {app_name}")
    print(f"Bundle app resource: {app_resource_key}")
    if profile:
        print(f"Databricks profile: {profile}")
    if ignored_cluster_id:
        print("Ignoring DATABRICKS_CLUSTER_ID for Databricks App deployment.")
    print("Bundle variables:")
    for key in sorted(bundle_vars):
        print(f"  {key}={bundle_vars[key]}")
    if runtime_env:
        print("Runtime env staged into app.yml during deploy:")
        for key in sorted(runtime_env):
            print(f"  {key}={runtime_env[key]}")
    else:
        print("Runtime env staged into app.yml during deploy: none")

    source_app_yml = project_dir / "app.yml"
    original_app_yml = source_app_yml.read_text()

    try:
        if not args.dry_run:
            write_runtime_env(source_app_yml, runtime_env)

        if not args.skip_build:
            run(
                ["apx", "build"],
                cwd=project_dir,
                env=process_env,
                dry_run=args.dry_run,
            )

        validate = command_with_profile(
            ["databricks", "bundle", "validate"],
            profile=profile,
            target=target,
            bundle_vars=bundle_vars,
        )
        run(validate, cwd=project_dir, env=process_env, dry_run=args.dry_run)

        if strict_validate:
            run(
                [*validate, "--strict"],
                cwd=project_dir,
                env=process_env,
                dry_run=args.dry_run,
            )

        run(
            command_with_profile(
                ["databricks", "bundle", "deploy"],
                profile=profile,
                target=target,
                bundle_vars=bundle_vars,
            ),
            cwd=project_dir,
            env=process_env,
            dry_run=args.dry_run,
        )
        run(
            command_with_profile(
                ["databricks", "bundle", "run", app_resource_key],
                profile=profile,
                target=target,
                bundle_vars=bundle_vars,
            ),
            cwd=project_dir,
            env=process_env,
            dry_run=args.dry_run,
        )
        run(
            command_with_profile(
                ["databricks", "bundle", "summary"],
                profile=profile,
                target=target,
                bundle_vars=bundle_vars,
            ),
            cwd=project_dir,
            env=process_env,
            dry_run=args.dry_run,
        )
        app_get = ["databricks", "apps", "get", app_name, "-o", "json"]
        if profile:
            app_get.extend(["--profile", profile])
        app_details = run_json(
            app_get,
            cwd=project_dir,
            env=process_env,
            dry_run=args.dry_run,
        )
        if app_details is not None:
            app_status = app_details.get("app_status")
            compute_status = app_details.get("compute_status")
            active_deployment = app_details.get("active_deployment")
            deployment_status = (
                active_deployment.get("status")
                if isinstance(active_deployment, dict)
                else None
            )

            print("Databricks app status:")
            print(f"  name: {app_details.get('name')}")
            print(f"  url: {app_details.get('url')}")
            if isinstance(app_status, dict):
                print(f"  app_state: {app_status.get('state')}")
            if isinstance(compute_status, dict):
                print(f"  compute_state: {compute_status.get('state')}")
            if isinstance(active_deployment, dict):
                print(f"  deployment_id: {active_deployment.get('deployment_id')}")
            if isinstance(deployment_status, dict):
                print(f"  deployment_state: {deployment_status.get('state')}")
    finally:
        if not args.dry_run:
            source_app_yml.write_text(original_app_yml)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"deploy_from_env.py: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
