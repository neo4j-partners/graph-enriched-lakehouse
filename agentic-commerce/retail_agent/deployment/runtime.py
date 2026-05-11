"""Runtime helpers for Databricks wheel entry points."""

from __future__ import annotations

import os
import sys


def inject_env_params() -> None:
    """Load KEY=VALUE Databricks job parameters into ``os.environ``.

    Databricks Python wheel tasks pass entry point parameters through
    ``sys.argv``. The project uses KEY=VALUE parameters so one uploaded wheel
    can run in different workspace/catalog/endpoint configurations.
    """
    remaining: list[str] = []
    for arg in sys.argv[1:]:
        if "=" in arg and not arg.startswith("-"):
            key, _, value = arg.partition("=")
            os.environ.setdefault(key, value)
        else:
            remaining.append(arg)
    sys.argv[1:] = remaining
