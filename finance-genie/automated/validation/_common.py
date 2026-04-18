"""Shared helpers for automated/validation/ scripts.

Sits alongside the validation scripts so they can do `from _common import …`
when run via `uv run validation/<script>.py` from `automated/` — Python adds
the script's directory to sys.path on launch, making the sibling import work
without package plumbing.

Exposes:
  fail(msg)                  print FAIL + sys.exit(1)
  ok(msg)                    print OK
  warn(msg)                  print WARN
  header(label)              print a section divider
  load_env(required_vars)    load automated/.env and verify required vars set
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

_AUTOMATED_DIR = Path(__file__).resolve().parent.parent
_ENV_PATH = _AUTOMATED_DIR / ".env"


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK    {msg}")


def warn(msg: str) -> None:
    print(f"WARN  {msg}")


def header(label: str) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))


def load_env(required: Iterable[str]) -> None:
    """Load automated/.env and verify the required vars are non-empty.

    Calls fail() with a clear message if .env is missing or any listed var
    is unset or empty. Path resolution is anchored to _common.py's location,
    so it works regardless of the caller's cwd.
    """
    if not _ENV_PATH.is_file():
        fail(f".env not found at {_ENV_PATH}")
    load_dotenv(_ENV_PATH, override=True)
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        fail(f"missing or empty in .env: {', '.join(missing)}")
