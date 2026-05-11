"""Deployment configuration for Agentic Commerce.

Usage:
    from retail_agent.agent.config import CONFIG, AGENT_NAME, RunMode
"""

import os
from dataclasses import dataclass, field
from enum import Enum

AGENT_DISPLAY_NAME = "Agentic Commerce"
AGENT_NAME = "retail_agent_v3"
DEFAULT_ENDPOINT_NAME = "agents_retail_assistant-retail-retail_agent_v3"


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean env var using common true/false spellings."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    """Read an integer env var, raising a useful error for invalid values."""
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _env_run_mode() -> "RunMode":
    value = os.environ.get("RETAIL_AGENT_RUN_MODE", RunMode.DEPLOY.value)
    try:
        return RunMode(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RunMode)
        raise ValueError(
            f"RETAIL_AGENT_RUN_MODE must be one of: {allowed}"
        ) from exc


class RunMode(Enum):
    """Deployment run modes."""

    DEPLOY = "deploy"
    DELETE = "delete"


@dataclass
class DeployConfig:
    """Configuration for deploying the Agentic Commerce agent to Databricks."""

    # Run mode
    run_mode: RunMode = field(default_factory=_env_run_mode)
    wait_for_ready: bool = field(
        default_factory=lambda: _env_bool("RETAIL_AGENT_WAIT_FOR_READY", True)
    )
    max_wait_seconds: int = field(
        default_factory=lambda: _env_int("RETAIL_AGENT_MAX_WAIT_SECONDS", 1200)
    )

    # Unity Catalog — matches existing lakehouse_tables.py naming
    catalog: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_CATALOG", "retail_assistant"
        )
    )
    schema: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_SCHEMA", "retail")
    )
    model_name: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_MODEL_NAME", AGENT_NAME)
    )

    # Endpoint name (auto-generated if empty)
    endpoint_name: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_ENDPOINT_NAME", "")
    )

    # MLflow
    experiment_name_pattern: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_EXPERIMENT_NAME_PATTERN",
            f"/Users/{{user}}/{AGENT_NAME}",
        )
    )
    run_name: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_RUN_NAME", AGENT_NAME)
    )
    artifact_path: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_ARTIFACT_PATH", AGENT_NAME)
    )

    # Databricks secrets (used in Step 3, not Step 2)
    secret_scope: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_SECRET_SCOPE", "retail-agent-secrets"
        )
    )
    neo4j_uri_secret: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_NEO4J_URI_SECRET", "neo4j-uri"
        )
    )
    neo4j_password_secret: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_NEO4J_PASSWORD_SECRET", "neo4j-password"
        )
    )

    # LLM — Databricks-hosted, no API key needed
    llm_endpoint: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_LLM_ENDPOINT", "databricks-claude-sonnet-4-6"
        )
    )

    # Embedding — Databricks Foundation Model API (pre-deployed, no setup needed)
    embedding_model: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_EMBEDDING_MODEL", "databricks-bge-large-en"
        )
    )
    embedding_dimensions: int = field(
        default_factory=lambda: _env_int("RETAIL_AGENT_EMBEDDING_DIMENSIONS", 1024)
    )

    # Deployment
    scale_to_zero: bool = field(
        default_factory=lambda: _env_bool("RETAIL_AGENT_SCALE_TO_ZERO", True)
    )
    validate_model: bool = field(
        default_factory=lambda: _env_bool("RETAIL_AGENT_VALIDATE_MODEL", True)
    )
    validation_env_manager: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_VALIDATION_ENV_MANAGER", "virtualenv"
        )
    )

    # Supervisor (STUB) — see retail_agent.agent.supervisor
    # Both fields must be set before the supervisor deploy entry point can do real work.
    supervisor_model_name: str = field(
        default_factory=lambda: os.environ.get(
            "RETAIL_AGENT_SUPERVISOR_MODEL_NAME", "retail_supervisor_v1"
        )
    )
    genie_space_id: str = field(
        default_factory=lambda: os.environ.get("RETAIL_AGENT_GENIE_SPACE_ID", "")
    )

    # Sample queries for testing
    sample_queries: list[str] = field(
        default_factory=lambda: [
            "Echo hello world",
            "Search for running shoes under $200",
            "Get details for product 'nike-pegasus-40'",
            "What products are related to 'brooks-ghost-16'?",
        ]
    )

    @property
    def uc_model_name(self) -> str:
        """Full Unity Catalog model name."""
        return f"{self.catalog}.{self.schema}.{self.model_name}"

    @property
    def resolved_endpoint_name(self) -> str:
        """Endpoint name used by Databricks Model Serving."""
        if self.endpoint_name:
            return self.endpoint_name
        return DEFAULT_ENDPOINT_NAME

    def get_experiment_name(self, user: str) -> str:
        """Get experiment name with user substitution."""
        return self.experiment_name_pattern.replace("{user}", user)

    def get_environment_vars(self) -> dict[str, str]:
        """Get secret-backed environment variables for the serving endpoint.

        Step 3: Neo4j secrets for MemoryClient connection.
        Uses the {{secrets/scope/key}} pattern per LANGCHAIN_AGENT.md Section 7.
        """
        return {
            "NEO4J_URI": f"{{{{secrets/{self.secret_scope}/{self.neo4j_uri_secret}}}}}",
            "NEO4J_PASSWORD": f"{{{{secrets/{self.secret_scope}/{self.neo4j_password_secret}}}}}",
            "RETAIL_AGENT_LLM_ENDPOINT": self.llm_endpoint,
            "RETAIL_AGENT_EMBEDDING_MODEL": self.embedding_model,
            "RETAIL_AGENT_EMBEDDING_DIMENSIONS": str(self.embedding_dimensions),
        }


CONFIG = DeployConfig()
