from __future__ import annotations

import logging
import sys
from importlib import resources
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..._metadata import app_name, app_slug

# --- Config ---

project_root = Path(__file__).parent.parent.parent.parent.parent
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file)


class AppConfig(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=env_file,
        env_prefix=f"{app_slug.upper()}_",
        extra="ignore",
        env_nested_delimiter="__",
    )
    app_name: str = Field(default=app_name)
    retail_agent_endpoint_name: str = Field(
        default="agents_retail_assistant-retail-retail_agent_v3"
    )
    retail_agent_timeout_seconds: int = Field(default=120)
    demo_data_mode: str = Field(default="live")
    demo_allow_sample_fallback: bool = Field(default=False)
    demo_include_raw_endpoint_metadata: bool = Field(default=False)

    @property
    def static_assets_path(self) -> Path:
        return Path(str(resources.files(app_slug))).joinpath("__dist__")

    def __hash__(self) -> int:
        return hash(self.app_name)


# --- Logger ---

logger = logging.getLogger(app_name)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)
logger.propagate = False
