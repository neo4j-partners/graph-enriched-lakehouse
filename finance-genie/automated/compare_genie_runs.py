"""Compare BEFORE and AFTER Genie run artifacts side-by-side.

Auto-discovers the most recent genie_run_before_*.json and
genie_run_after_*.json from RESULTS_VOLUME_DIR, downloads them locally,
and emits a markdown side-by-side report plus an E2E summary line.

Usage (from finance-genie/automated/ with .env in place):
    uv run compare_genie_runs.py

Override discovery with explicit artifact paths on the volume:
    uv run compare_genie_runs.py \\
        --before-path /Volumes/.../genie_run_before_2026-04-18T17-00-00Z.json \\
        --after-path  /Volumes/.../genie_run_after_2026-04-18T17-10-00Z.json
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from dotenv import load_dotenv

# Load automated/.env — works regardless of the caller's cwd.
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.is_file():
    load_dotenv(_ENV_PATH, override=True)

from databricks.sdk import WorkspaceClient  # noqa: E402
from databricks_job_runner.download import download_file, list_volume_files  # noqa: E402

# jobs/ hosts the shared artifact schema; it is not on the default import path
# because cluster-side modules also live there. Insert it so we can import the
# schema without pulling in cluster-only bootstrap code.
sys.path.insert(0, str(Path(__file__).resolve().parent / "jobs"))
from genie_run_artifact import (  # noqa: E402
    ArtifactSchemaError,
    case_by_name,
    last_attempt,
    load_run_artifact,
    metric_key,
    metric_value,
)

RESULTS_VOLUME_DIR = os.environ.get("RESULTS_VOLUME_DIR", "").rstrip("/")
_HERE = Path(__file__).resolve().parent
LOGS_DIR = _HERE / "logs"


# --------------------------------------------------------------------------- #
# Discovery                                                                    #
# --------------------------------------------------------------------------- #

def _discover_artifact(ws: WorkspaceClient, label: str) -> str:
    """Return the full remote path of the most recent genie_run_<label>_*.json."""
    prefix = f"genie_run_{label}_"
    try:
        names = list_volume_files(ws, RESULTS_VOLUME_DIR)
    except Exception as exc:
        _die(f"cannot list {RESULTS_VOLUME_DIR}: {exc}")

    matches = sorted(n for n in names if n.startswith(prefix) and n.endswith(".json"))
    if not matches:
        _die(
            f"no artifact matching '{prefix}*.json' found in {RESULTS_VOLUME_DIR}.\n"
            f"  Run: python -m cli submit genie_run.py GENIE_SPACE_ID=... LABEL={label}\n"
            f"  Or pass --{label}-path explicitly."
        )
    latest = matches[-1]
    return f"{RESULTS_VOLUME_DIR}/{latest}"


# --------------------------------------------------------------------------- #
# Markdown report                                                              #
# --------------------------------------------------------------------------- #

def _fmt(val: float | None, precision: int = 2) -> str:
    if val is None:
        return "n/a"
    return f"{val:.{precision}f}"


def _sql_preview(case: dict | None) -> str:
    a = last_attempt(case)
    sql = a.get("genie_sql") or ""
    if not sql:
        return "*(none)*"
    return f"`{sql[:120]}{'…' if len(sql) > 120 else ''}`"


def _top_rows_md(case: dict | None, n: int = 3) -> str:
    a = last_attempt(case)
    rows = (a.get("result_preview_records") or [])[:n]
    if not rows:
        return "*(no data)*"
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def build_report(before: dict, after: dict, compare_ts: str) -> str:
    lines: list[str] = []
    lines.append(f"# Genie BEFORE vs. AFTER — {compare_ts}")
    lines.append("")

    b_cases = case_by_name(before)
    a_cases = case_by_name(after)
    b_resp = before.get("summary", {}).get("responded", 0)
    b_total = before.get("summary", {}).get("total", 3)
    a_resp = after.get("summary", {}).get("responded", 0)
    a_total = after.get("summary", {}).get("total", 3)

    lines.append("## Summary")
    lines.append(
        f"- BEFORE space: `{before.get('space_id', 'unknown')}`  "
        f"label={before.get('label', '?')}  ({b_resp}/{b_total} responded)"
    )
    lines.append(
        f"- AFTER space: `{after.get('space_id', 'unknown')}`  "
        f"label={after.get('label', '?')}  ({a_resp}/{a_total} responded)"
    )
    lines.append("- Metric deltas (AFTER − BEFORE):")

    all_names = [c["name"] for c in before.get("cases", [])]
    if not all_names:
        all_names = [c["name"] for c in after.get("cases", [])]

    for name in all_names:
        b_val = metric_value(b_cases.get(name))
        a_val = metric_value(a_cases.get(name))
        key = metric_key(a_cases.get(name) or b_cases.get(name))
        if b_val is not None and a_val is not None:
            delta = a_val - b_val
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"  - {name}.{key}: {sign}{delta:.2f}  ({_fmt(b_val)} → {_fmt(a_val)})"
            )
        else:
            lines.append(f"  - {name}.{key}: n/a")

    lines.append("")

    for name in all_names:
        bc = b_cases.get(name)
        ac = a_cases.get(name)
        question = (bc or ac or {}).get("question", name)
        lines.append(f"## {name} — \"{question}\"")
        lines.append("")

        b_rows = (last_attempt(bc).get("row_count") or 0)
        a_rows = (last_attempt(ac).get("row_count") or 0)
        b_mval = _fmt(metric_value(bc))
        a_mval = _fmt(metric_value(ac))
        mk = metric_key(ac or bc)

        lines.append("| | BEFORE | AFTER |")
        lines.append("|---|---|---|")
        lines.append(f"| SQL | {_sql_preview(bc)} | {_sql_preview(ac)} |")
        lines.append(f"| Rows returned | {b_rows} | {a_rows} |")
        lines.append(f"| Metric ({mk}) | {b_mval} | {a_mval} |")
        lines.append("")
        lines.append("**BEFORE — top 3 rows:**")
        lines.append("")
        lines.append(_top_rows_md(bc))
        lines.append("")
        lines.append("**AFTER — top 3 rows:**")
        lines.append("")
        lines.append(_top_rows_md(ac))
        lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _die(msg: str) -> NoReturn:
    print(f"FAIL  {msg}", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before-path", help="Full remote path to the BEFORE artifact (skips auto-discovery)")
    parser.add_argument("--after-path", help="Full remote path to the AFTER artifact (skips auto-discovery)")
    args = parser.parse_args()

    if not RESULTS_VOLUME_DIR:
        _die("RESULTS_VOLUME_DIR is not set. Check automated/.env.")

    _profile = os.environ.get("DATABRICKS_PROFILE") or None
    w = WorkspaceClient(profile=_profile)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Discover or accept explicit paths ---
    before_remote = args.before_path or _discover_artifact(w, "before")
    after_remote = args.after_path or _discover_artifact(w, "after")

    print(f"BEFORE artifact: {before_remote}")
    print(f"AFTER  artifact: {after_remote}")

    # --- Download locally ---
    before_local = LOGS_DIR / Path(before_remote).name
    after_local = LOGS_DIR / Path(after_remote).name

    print("\nDownloading artifacts...")
    download_file(w, before_remote, before_local)
    download_file(w, after_remote, after_local)

    try:
        before = load_run_artifact(before_local)
        after = load_run_artifact(after_local)
    except ArtifactSchemaError as exc:
        _die(str(exc))

    # --- Build report ---
    compare_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = build_report(before, after, compare_ts)

    report_name = f"compare_{compare_ts.replace(':', '-').replace('.', '-')}.md"
    report_path = LOGS_DIR / report_name
    report_path.write_text(report, encoding="utf-8")

    print()
    print(report)
    print(f"Report written to: {report_path}")

    # --- E2E summary ---
    b_resp = before.get("summary", {}).get("responded", 0)
    b_total = before.get("summary", {}).get("total", 3)
    a_resp = after.get("summary", {}).get("responded", 0)
    a_total = after.get("summary", {}).get("total", 3)
    total_responded = b_resp + a_resp
    total_questions = b_total + a_total

    if total_responded == total_questions:
        print(f"E2E PASS — {total_responded}/{total_questions} Genie questions returned data")
    else:
        missing = total_questions - total_responded
        print(
            f"E2E FAIL — {missing} Genie question(s) did not return data "
            f"({total_responded}/{total_questions} responded)"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
