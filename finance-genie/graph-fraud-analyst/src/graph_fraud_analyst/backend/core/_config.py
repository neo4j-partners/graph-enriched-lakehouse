from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..._metadata import app_name, app_slug

# --- Config ---

project_root = Path(__file__).parent.parent.parent.parent.parent
shared_env_file = project_root.parent / ".env"
env_file = project_root / ".env"

if shared_env_file.exists():
    load_dotenv(dotenv_path=shared_env_file)
if env_file.exists():
    load_dotenv(dotenv_path=env_file)


class AppConfig(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=env_file,
        env_prefix=f"{app_slug.upper()}_",
        extra="ignore",
        env_nested_delimiter="__",
        populate_by_name=True,
    )
    app_name: str = Field(default=app_name)

    # Databricks runtime configuration. Required at request time, but defaulted
    # so the app can boot in environments where they are not yet wired up. The
    # service modules raise a clear error when they need an unset value.
    warehouse_id: str = Field(default="")
    """SQL warehouse ID for statement execution against gold tables."""

    catalog: str = Field(default="graph-enriched-lakehouse")
    """Unity Catalog catalog name holding the gold tables. Matches the names
    produced by the automated/ pipeline (hyphens, quoted with backticks in
    SQL)."""

    schema_: str = Field(default="graph-enriched-schema", alias="schema")
    """Unity Catalog schema name holding the gold tables. Aliased from `schema`
    because BaseSettings reserves the `schema` attribute name."""

    genie_space_id: str = Field(default="")
    """Genie Space ID for the AFTER-GDS Conversation API."""

    @property
    def static_assets_path(self) -> Path:
        return Path(str(resources.files(app_slug))).joinpath("__dist__")

    def __hash__(self) -> int:
        return hash(self.app_name)


# --- Logger ---

logger = logging.getLogger(app_name)
