"""Cluster bootstrap helpers — imported by job scripts running on Databricks.

The databricks_job_runner package is local-only and not installed on the
cluster. Uploading this module alongside the job scripts lets each job import
two utilities here instead of duplicating 15 lines of boilerplate.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def inject_params() -> None:
    """Parse KEY=VALUE argv parameters into os.environ.

    The CLI runner forwards .env variables as positional KEY=VALUE args.
    Uses setdefault so pre-existing environment variables take precedence,
    matching standard 12-factor semantics.
    """
    remaining: list[str] = []
    for arg in sys.argv[1:]:
        if "=" in arg and not arg.startswith("-"):
            key, _, value = arg.partition("=")
            os.environ.setdefault(key, value)
        else:
            remaining.append(arg)
    sys.argv[1:] = remaining


def resolve_here() -> Path:
    """Return the directory of the calling module.

    Works when __file__ is not defined — which happens when Databricks runs a
    script via exec(compile(source, filename, 'exec')). In that case
    frame.f_back.f_code.co_filename is still populated with the correct path.
    """
    import inspect
    frame = inspect.currentframe()
    try:
        return Path(frame.f_back.f_code.co_filename).resolve().parent
    finally:
        del frame
