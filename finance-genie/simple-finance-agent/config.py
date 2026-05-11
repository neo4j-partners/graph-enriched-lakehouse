"""Configuration for the simple finance agent demo."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

DEMO_DIR = Path(__file__).resolve().parent
ENV_PATH = DEMO_DIR / ".env"
ROOT_ENV_PATH = DEMO_DIR.parent / ".env"

load_dotenv(ROOT_ENV_PATH, override=False)
load_dotenv(ENV_PATH, override=False)


class Settings(BaseModel):
    """Typed settings shared by local validation, jobs, and agent code."""

    model_config = ConfigDict(frozen=True)

    databricks_profile: str | None = Field(default=None, alias="DATABRICKS_PROFILE")
    databricks_compute_mode: str = Field(default="cluster", alias="DATABRICKS_COMPUTE_MODE")
    databricks_cluster_id: str | None = Field(default=None, alias="DATABRICKS_CLUSTER_ID")
    databricks_serverless_env_version: str = Field(
        default="3", alias="DATABRICKS_SERVERLESS_ENV_VERSION"
    )
    databricks_workspace_dir: str | None = Field(
        default=None,
        alias="DATABRICKS_WORKSPACE_DIR",
        validation_alias=AliasChoices(
            "SIMPLE_FINANCE_AGENT_DATABRICKS_WORKSPACE_DIR",
            "DATABRICKS_WORKSPACE_DIR",
        ),
    )
    catalog: str = Field(default="graph-on-databricks", alias="CATALOG")
    schema_name: str = Field(default="graph-enriched-schema", alias="SCHEMA")

    uc_connection_name: str = Field(
        default="neo4j_agentcore_mcp", alias="UC_CONNECTION_NAME"
    )

    llm_endpoint_name: str = Field(
        default="databricks-claude-sonnet-4-6", alias="LLM_ENDPOINT_NAME"
    )
    uc_model_name: str = Field(
        default="simple-finance-agent",
        alias="UC_MODEL_NAME",
        validation_alias=AliasChoices(
            "SIMPLE_FINANCE_AGENT_UC_MODEL_NAME",
            "UC_MODEL_NAME",
        ),
    )
    model_serving_endpoint_name: str = Field(
        default="simple-finance-agent",
        alias="MODEL_SERVING_ENDPOINT_NAME",
        validation_alias=AliasChoices(
            "SIMPLE_FINANCE_AGENT_MODEL_SERVING_ENDPOINT_NAME",
            "MODEL_SERVING_ENDPOINT_NAME",
        ),
    )
    smoke_test_prompt: str = Field(
        default=(
            "Use the Neo4j MCP read-only Cypher tool with exactly this query: "
            "RETURN 1 AS ok. Return the result and mention that the MCP tool "
            "call succeeded."
        ),
        alias="SMOKE_TEST_PROMPT",
        validation_alias=AliasChoices(
            "SIMPLE_FINANCE_AGENT_SMOKE_TEST_PROMPT",
            "SMOKE_TEST_PROMPT",
        ),
    )

    @field_validator("*", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def full_uc_model_name(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.uc_model_name}"

    @property
    def external_mcp_path(self) -> str:
        return f"/api/2.0/mcp/external/{self.uc_connection_name}"


def load_settings() -> Settings:
    return Settings.model_validate(dict(os.environ))


settings = load_settings()
