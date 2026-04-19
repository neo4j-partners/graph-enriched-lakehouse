"""Shared schema + loader for genie_run_*.json artifacts.

Both genie_run_before.py and genie_run_after.py write artifacts in this shape.
Keeping the keys in one place means a rename surfaces at both ends instead of
producing a silent KeyError downstream.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, TypedDict


# --------------------------------------------------------------------------- #
# TypedDict schema                                                             #
# --------------------------------------------------------------------------- #

class Metric(TypedDict, total=False):
    key: str
    value: float | None
    after_gate_criterion: str
    meets_after_gate: bool


class Attempt(TypedDict, total=False):
    attempt: int
    error: str | None
    genie_sql: str | None
    genie_response_text: str | None
    row_count: int
    result_preview_records: list[dict]
    metric: Metric | None
    traceback: str


class Case(TypedDict, total=False):
    name: str
    question: str
    responded: bool
    attempts_made: int
    attempts: list[Attempt]
    metric: Metric | None


class Summary(TypedDict):
    responded: int
    total: int
    meets_after_gate: int


class RunArtifact(TypedDict):
    space_id: str
    label: str
    timestamp_utc: str
    gate_enabled: bool
    retries_configured: int
    summary: Summary
    cases: list[Case]


# Top-level keys the loader enforces. Per-case keys are validated loosely
# because older artifacts may be missing newer optional fields.
_REQUIRED_TOP_LEVEL = ("space_id", "label", "timestamp_utc", "summary", "cases")
_REQUIRED_CASE = ("name", "question", "attempts")
_REQUIRED_SUMMARY = ("responded", "total")


class ArtifactSchemaError(ValueError):
    """Raised when a run artifact is missing required keys."""


def load_run_artifact(path: str | Path) -> RunArtifact:
    """Read a genie_run_*.json artifact and validate its shape.

    Raises ArtifactSchemaError with a specific message naming the missing key
    so schema drift produces a clear error instead of a silent KeyError
    downstream. Returns the parsed dict (typed as RunArtifact for callers).
    """
    data: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArtifactSchemaError(f"{path}: expected JSON object at top level, got {type(data).__name__}")

    _require_keys(data, _REQUIRED_TOP_LEVEL, context=str(path))
    _require_keys(data["summary"], _REQUIRED_SUMMARY, context=f"{path}:summary")

    cases = data["cases"]
    if not isinstance(cases, list):
        raise ArtifactSchemaError(f"{path}:cases: expected list, got {type(cases).__name__}")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ArtifactSchemaError(f"{path}:cases[{i}]: expected object, got {type(case).__name__}")
        _require_keys(case, _REQUIRED_CASE, context=f"{path}:cases[{i}]")

    return data  # type: ignore[return-value]


def _require_keys(obj: dict, required: tuple[str, ...], *, context: str) -> None:
    missing = [k for k in required if k not in obj]
    if missing:
        raise ArtifactSchemaError(f"{context}: missing required key(s) {missing}")


# --------------------------------------------------------------------------- #
# Read-side helpers                                                            #
# --------------------------------------------------------------------------- #

def case_by_name(artifact: RunArtifact) -> dict[str, Case]:
    return {c["name"]: c for c in artifact.get("cases", [])}


def metric_value(case: Case | None) -> float | None:
    if case is None:
        return None
    m = case.get("metric")
    if m is None:
        return None
    return m.get("value")


def metric_key(case: Case | None) -> str:
    if case is None:
        return "metric"
    m = case.get("metric")
    if m is None:
        return "metric"
    return m.get("key", "metric")


def last_attempt(case: Case | None) -> Attempt:
    if case is None:
        return {}  # type: ignore[typeddict-item]
    attempts = case.get("attempts") or []
    return attempts[-1] if attempts else {}  # type: ignore[typeddict-item]


def sql_preview(result: dict, max_chars: int = 220) -> str:
    if not result["attempts"]:
        return "(no SQL)"
    sql = (result["attempts"][-1].get("genie_sql") or "").strip()
    if not sql:
        return "(no SQL)"
    single_line = " ".join(sql.split())
    return single_line[:max_chars] + "…" if len(single_line) > max_chars else single_line


def wrap_text(text: str, indent: int = 14, width: int = 78) -> str:
    pad = " " * indent
    wrapped = textwrap.wrap(text, width=max(width - indent, 20)) or [text]
    return ("\n" + pad).join(wrapped)
