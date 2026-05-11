"""Deploy Agentic Commerce to Databricks using agents.deploy().

Ported from aircraft_analyst/src/graph_agent/deploy.py. Four-step
pipeline: log model -> register to UC -> deploy -> wait for ready.

Runs on a Databricks cluster or as a Databricks Job.

    # Delete mode:
    Set environment variable RETAIL_AGENT_RUN_MODE=delete before running.

Prerequisites:
    1. Databricks CLI configured (databricks auth login)
    2. Unity Catalog: retail_assistant.retail must exist
    3. For Step 3 (not Step 2): Databricks secrets for Neo4j
"""

import os
import sys
import time
from pathlib import Path
from typing import Any

from retail_agent.agent.config import CONFIG, DeployConfig, RunMode
from retail_agent.deployment.runtime import inject_env_params


def _get_package_dir() -> Path:
    """Resolve the retail_agent package directory.

    Uses __file__ when available (local CLI). On Databricks, Python
    files run through IPython where __file__ is not defined, so we
    fall back to inspecting the config module's file location (which
    *is* set because it was imported normally, not executed directly).
    """
    # Try __file__ first (works when running as `python -m retail_agent...`)
    this_file = globals().get("__file__")
    if this_file:
        return Path(this_file).parents[1]

    # Databricks Workspace: the directly-executed file has no __file__,
    # but imported modules do. config.py lives in retail_agent/agent/.
    import retail_agent.agent.config as _cfg

    cfg_file = getattr(_cfg, "__file__", None)
    if cfg_file:
        return Path(cfg_file).parents[1]

    raise RuntimeError(
        "Cannot determine retail_agent package directory: neither __file__ nor "
        "retail_agent.agent.config.__file__ is available."
    )


def get_current_user() -> str:
    """Get the current Databricks user email."""
    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        return w.current_user.me().user_name
    except Exception:
        return os.environ.get("DATABRICKS_USER", "default")


def _restore_env_var(name: str, previous: str | None) -> None:
    """Restore an env var after temporarily changing it."""
    if previous is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = previous


def validate_logged_model(model_uri: str, config: DeployConfig) -> None:
    """Validate that the logged model loads and accepts ChatAgent input."""
    import mlflow

    print()
    print("=" * 60)
    print("STEP 1B: Validate Logged Model")
    print("=" * 60)
    print(f"Model URI: {model_uri}")
    print(f"Environment manager: {config.validation_env_manager}")

    input_example = {
        "messages": [{"role": "user", "content": "Echo validation"}],
        "custom_inputs": {
            "session_id": "deployment-validation",
            "demo_mode": "off",
        },
    }
    result = mlflow.models.predict(
        model_uri=model_uri,
        input_data=input_example,
        env_manager=config.validation_env_manager,
    )
    if result is None:
        print("Logged model validation completed without a returned payload")
    else:
        print("Logged model validation passed")


# =============================================================================
# STEP 1: LOG MODEL TO MLFLOW
# =============================================================================


def log_model_to_mlflow(config: DeployConfig) -> tuple:
    """Log the agent model to MLflow using Models from Code."""
    import mlflow
    from mlflow.models.resources import DatabricksServingEndpoint

    print("=" * 60)
    print("STEP 1: Log Model to MLflow")
    print("=" * 60)

    mlflow.set_registry_uri("databricks-uc")

    current_user = get_current_user()
    experiment_name = config.get_experiment_name(current_user)
    mlflow.set_experiment(experiment_name)
    print(f"Experiment: {experiment_name}")

    package_dir = _get_package_dir()

    # MLflow loads this file via Models from Code.
    model_file = package_dir / "agent" / "serving.py"
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    print(f"Model file: {model_file}")

    # Package imported by serving.py at runtime.
    code_files = [str(package_dir)]

    print(f"Including code paths: {[Path(f).name for f in code_files]}")

    pip_requirements = [
        "mlflow==3.12.0",
        "databricks-agents==1.10.1",
        "langgraph==1.1.10",
        "langgraph-prebuilt==1.0.13",
        "langgraph-sdk==0.3.7",
        "langchain-core==1.3.3",
        "databricks-langchain==0.19.0",
        "neo4j==6.2.0",
        "neo4j-agent-memory==0.2.1",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "openai>=1.0.0",
        "nest-asyncio>=1.5.0",
    ]

    input_example = {
        "messages": [{"role": "user", "content": "Echo validation"}],
        "custom_inputs": {
            "session_id": "deployment-validation",
            "demo_mode": "off",
        },
    }
    resources = [
        DatabricksServingEndpoint(endpoint_name=config.llm_endpoint),
        DatabricksServingEndpoint(endpoint_name=config.embedding_model),
    ]

    previous_allow = os.environ.get("RETAIL_AGENT_ALLOW_UNINITIALIZED_FOR_LOGGING")
    os.environ["RETAIL_AGENT_ALLOW_UNINITIALIZED_FOR_LOGGING"] = "1"
    try:
        with mlflow.start_run(run_name=config.run_name):
            log_kwargs = {
                "artifact_path": config.artifact_path,
                "python_model": str(model_file),
                "pip_requirements": pip_requirements,
                "code_paths": code_files,
                "input_example": input_example,
                "resources": resources,
            }

            model_info = mlflow.pyfunc.log_model(**log_kwargs)
            print(f"Model logged: {model_info.model_uri}")

            if config.validate_model:
                validate_logged_model(model_info.model_uri, config)
            else:
                print("Skipping logged model validation")

            return model_info, model_info.model_uri
    finally:
        _restore_env_var(
            "RETAIL_AGENT_ALLOW_UNINITIALIZED_FOR_LOGGING",
            previous_allow,
        )


# =============================================================================
# STEP 2: REGISTER TO UNITY CATALOG
# =============================================================================


def register_model_to_uc(model_uri: str, config: DeployConfig):
    """Register the model to Unity Catalog."""
    import mlflow

    print()
    print("=" * 60)
    print("STEP 2: Register to Unity Catalog")
    print("=" * 60)

    registered_model = mlflow.register_model(
        model_uri=model_uri,
        name=config.uc_model_name,
    )
    print(f"Registered: {registered_model.name}")
    print(f"Version: {registered_model.version}")
    return registered_model


# =============================================================================
# STEP 3: DEPLOY USING agents.deploy()
# =============================================================================


def deploy_agent(config: DeployConfig, model_version: int):
    """Deploy the agent using Databricks Agent Framework."""
    from databricks import agents

    print()
    print("=" * 60)
    print("STEP 3: Deploy with agents.deploy()")
    print("=" * 60)

    print(f"Model: {config.uc_model_name}")
    print(f"Version: {model_version}")
    print(f"Endpoint: {config.resolved_endpoint_name}")
    print(f"Scale to zero: {config.scale_to_zero}")

    env_vars = config.get_environment_vars()
    if env_vars:
        print("\nEnvironment variables:")
        for key, value in env_vars.items():
            display_value = "{{secrets/...}}" if "secrets/" in value else value
            print(f"  {key}: {display_value}")
    else:
        print("\nNo environment variables (Step 2 — no secrets needed)")

    deploy_kwargs = {
        "endpoint_name": config.resolved_endpoint_name,
        "scale_to_zero": config.scale_to_zero,
    }
    if env_vars:
        deploy_kwargs["environment_vars"] = env_vars

    deployment = agents.deploy(
        config.uc_model_name,
        model_version,
        **deploy_kwargs,
    )

    print()
    print("Deployment initiated!")
    print(f"Query endpoint: {deployment.query_endpoint}")
    return deployment


# =============================================================================
# STEP 4: WAIT FOR ENDPOINT TO BE READY
# =============================================================================


def _enum_value(value: Any) -> str | None:
    """Return a stable string for SDK enum/string values."""
    if value is None:
        return None
    return getattr(value, "value", str(value))


def _served_entity_version(entity: Any) -> str | None:
    return (
        getattr(entity, "entity_version", None)
        or getattr(entity, "model_version", None)
    )


def _served_entity_name(entity: Any) -> str | None:
    return getattr(entity, "name", None)


def _active_routes(endpoint: Any) -> list[Any]:
    config = getattr(endpoint, "config", None)
    traffic_config = getattr(config, "traffic_config", None)
    return list(getattr(traffic_config, "routes", None) or [])


def _route_target_name(route: Any) -> str | None:
    return (
        getattr(route, "served_entity_name", None)
        or getattr(route, "served_model_name", None)
    )


def _target_version_receiving_traffic(
    endpoint: Any, expected_model_version: str | None
) -> bool:
    if expected_model_version is None:
        return True

    config = getattr(endpoint, "config", None)
    entities = list(getattr(config, "served_entities", None) or [])
    target_names = {
        _served_entity_name(entity)
        for entity in entities
        if _served_entity_version(entity) == expected_model_version
    }
    target_names.discard(None)
    if not target_names:
        return False

    return any(
        _route_target_name(route) in target_names
        and getattr(route, "traffic_percentage", 0) > 0
        for route in _active_routes(endpoint)
    )


def wait_for_endpoint(
    config: DeployConfig,
    endpoint_name: str,
    expected_model_version: str | None = None,
) -> bool:
    """Wait for the endpoint to be ready."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import EndpointStateReady

    print()
    print("=" * 60)
    print("STEP 4: Wait for Endpoint Ready")
    print("=" * 60)

    print(f"Endpoint: {endpoint_name}")
    if expected_model_version:
        print(f"Expected model version: {expected_model_version}")
    print(f"Max wait: {config.max_wait_seconds} seconds")
    print()

    w = WorkspaceClient()
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > config.max_wait_seconds:
            print(f"\nTimeout after {elapsed:.0f} seconds")
            return False

        try:
            endpoint = w.serving_endpoints.get(endpoint_name)
            state = endpoint.state.ready if endpoint.state else None
            config_update = (
                _enum_value(getattr(endpoint.state, "config_update", None))
                if endpoint.state
                else None
            )
            pending_config = getattr(endpoint, "pending_config", None)
            target_ready = _target_version_receiving_traffic(
                endpoint, expected_model_version
            )

            if (
                state == EndpointStateReady.READY
                and config_update != "IN_PROGRESS"
                and pending_config is None
                and target_ready
            ):
                print(
                    f"\nEndpoint is READY after {elapsed:.0f} seconds "
                    "and target version is receiving traffic"
                )
                return True

            print(
                f"  [{elapsed:>5.0f}s] State: {state}; "
                f"config_update={config_update}; "
                f"pending={pending_config is not None}; "
                f"target_traffic={target_ready}"
            )
            time.sleep(10)

        except Exception as e:
            print(f"  [{elapsed:>5.0f}s] Checking... ({e})")
            time.sleep(10)


# =============================================================================
# DELETE ENDPOINT
# =============================================================================


def delete_endpoint(config: DeployConfig) -> bool:
    """Delete the serving endpoint."""
    from databricks.sdk import WorkspaceClient

    print()
    print("=" * 60)
    print("DELETE ENDPOINT")
    print("=" * 60)

    endpoint_name = config.resolved_endpoint_name
    print(f"Endpoint to delete: {endpoint_name}")

    w = WorkspaceClient()
    try:
        try:
            endpoint = w.serving_endpoints.get(endpoint_name)
            print(f"Found endpoint: {endpoint.name}")
        except Exception:
            print(f"Endpoint '{endpoint_name}' does not exist")
            return True

        print("Deleting endpoint...")
        w.serving_endpoints.delete(endpoint_name)
        print("Endpoint deleted successfully")
        return True
    except Exception as e:
        print(f"Error deleting endpoint: {e}")
        return False


# =============================================================================
# MAIN
# =============================================================================


def print_config(config: DeployConfig) -> None:
    """Print the current configuration."""
    print("=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print(f"Run Mode:            {config.run_mode.value}")
    print(f"Unity Catalog Model: {config.uc_model_name}")
    print(f"Endpoint Name:       {config.resolved_endpoint_name}")
    print(f"LLM Endpoint:        {config.llm_endpoint}")
    print(f"Scale to Zero:       {config.scale_to_zero}")
    if config.run_mode == RunMode.DEPLOY:
        print(f"Experiment Pattern:  {config.experiment_name_pattern}")
        print(f"Wait for Ready:      {config.wait_for_ready}")
    print()
    print("Override with env vars: RETAIL_AGENT_CATALOG, RETAIL_AGENT_SCHEMA, etc.")
    print()


def run_deploy(config: DeployConfig) -> int:
    """Run the deployment workflow."""
    try:
        model_info, model_uri = log_model_to_mlflow(config)
        registered_model = register_model_to_uc(model_uri, config)
        deployment = deploy_agent(config, registered_model.version)

        if config.wait_for_ready:
            endpoint_name = (
                deployment.endpoint_name
                if hasattr(deployment, "endpoint_name")
                else config.resolved_endpoint_name
            )
            if not wait_for_endpoint(
                config, endpoint_name, str(registered_model.version)
            ):
                print("\nEndpoint not ready within timeout")
                print("Check the Databricks UI for status")
                return 1

        print()
        print("=" * 60)
        print("DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print()
        print(f"Query endpoint: {deployment.query_endpoint}")
        print()
        print("To test:")
        print("  Submit retail-agent-demo to verify the endpoint.")
        print()
        return 0

    except Exception as e:
        print()
        print("=" * 60)
        print(f"DEPLOYMENT FAILED: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        return 1


def run_delete(config: DeployConfig) -> int:
    """Run the delete workflow."""
    if delete_endpoint(config):
        print()
        print("=" * 60)
        print("DELETE COMPLETE!")
        print("=" * 60)
        return 0
    else:
        print()
        print("=" * 60)
        print("DELETE FAILED!")
        print("=" * 60)
        return 1


def main() -> int:
    """Main entry point."""
    inject_env_params()

    print()
    print("=" * 60)
    print("RETAIL AGENT DEPLOYMENT")
    print("=" * 60)
    print()

    config = CONFIG
    print_config(config)

    if config.run_mode == RunMode.DELETE:
        return run_delete(config)
    else:
        return run_deploy(config)


if __name__ == "__main__":
    sys.exit(main())
