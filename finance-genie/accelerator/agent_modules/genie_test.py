"""Automated Genie test runner for the GDS-enriched fraud-detection space.

Runs three validation questions against a Genie Space, scores the responses
against ground truth, prints a pass/fail table, and writes a JSON artifact to a
UC Volume. Exits non-zero on any failure so it can be used as a CI gate.

The three checks mirror genie_demos/gds_enrichment_closes_gaps.ipynb:
  1. hub_detection        — top-20 risk_score precision > 0.70
  2. community_structure  — max Louvain ring coverage > 0.80
  3. similarity_pairs     — top-20 same-ring fraction > 0.60

Usage (from finance-genie/accelerator/ with .env in place):
    python -m cli upload --all
    python -m cli submit genie_test.py
    python -m cli logs

Companion file:
    agent_modules/demo_utils.py ships alongside this script (both get uploaded
    by `python -m cli upload --all`). It is a project-local trim of
    genie_demos/demo_utils.py — only the three after-GDS check functions this
    runner needs.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Load .env extras forwarded by the runner as KEY=VALUE argv               #
#    (inlined from databricks_job_runner.inject — not installed on cluster)   #
# --------------------------------------------------------------------------- #
remaining: list[str] = []
for _arg in sys.argv[1:]:
    if "=" in _arg and not _arg.startswith("-"):
        _key, _, _val = _arg.partition("=")
        os.environ.setdefault(_key, _val)
    else:
        remaining.append(_arg)
sys.argv[1:] = remaining

# --------------------------------------------------------------------------- #
# 2. Import shared check helpers from the sibling demo_utils.py               #
# --------------------------------------------------------------------------- #
try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    # exec(compile(f.read(), filename, 'exec')) sets co_filename but not __file__
    import inspect as _inspect
    _HERE = Path(_inspect.currentframe().f_code.co_filename).resolve().parent
    del _inspect
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from demo_utils import (  # noqa: E402
    ask_genie,
    check_community_purity,
    check_risk_score_precision,
    check_ring_pair_fraction,
    load_ground_truth,
)
from databricks.sdk import WorkspaceClient  # noqa: E402

# --------------------------------------------------------------------------- #
# 3. Config                                                                   #
# --------------------------------------------------------------------------- #
SPACE_ID = os.environ["GENIE_SPACE_ID"]
GROUND_TRUTH_PATH = os.environ["GROUND_TRUTH_PATH"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")
RETRIES = int(os.environ.get("GENIE_TEST_RETRIES", "2"))
TIMEOUT_SECONDS = int(os.environ.get("GENIE_TEST_TIMEOUT_SECONDS", "120"))


def _hub_detection_check(df, gt):
    return check_risk_score_precision(df, gt, topn=20)


def _community_check(df, gt):
    return check_community_purity(df, gt["rings"])


def _similarity_check(df, gt):
    account_cols = [c for c in df.columns if "account" in c.lower()]
    if len(account_cols) < 2:
        return {
            "same_ring_fraction": 0.0,
            "total_pairs": 0,
            "same_ring_pairs": 0,
            "cross_ring_pairs": 0,
            "unknown_pairs": 0,
            "rings_touched": 0,
            "passed": False,
            "error": f"expected two account columns in result, got {list(df.columns)}",
        }
    a_col, b_col = account_cols[0], account_cols[1]
    pairs = list(zip(df[a_col].astype(int), df[b_col].astype(int)))
    return check_ring_pair_fraction(pairs, gt["rings"])


TEST_CASES = [
    {
        "name": "hub_detection",
        "question": (
            "Which accounts have the highest fraud risk based on their "
            "transfer network position?"
        ),
        "check_fn": _hub_detection_check,
        "metric_key": "precision",
    },
    {
        "name": "community_structure",
        "question": (
            "Find groups of accounts that form suspicious transaction "
            "communities based on their transfer patterns."
        ),
        "check_fn": _community_check,
        "metric_key": "max_ring_coverage",
    },
    {
        "name": "similarity_pairs",
        "question": (
            "Which pairs of accounts share the most similar merchant visit "
            "patterns?"
        ),
        "check_fn": _similarity_check,
        "metric_key": "same_ring_fraction",
    },
]


# --------------------------------------------------------------------------- #
# 4. Run the checks                                                            #
# --------------------------------------------------------------------------- #
def _run_case(w: WorkspaceClient, case: dict, gt: dict) -> dict:
    attempts: list[dict] = []
    passed = False
    metric_value: float | None = None

    for attempt_idx in range(1, RETRIES + 1):
        try:
            response = ask_genie(
                w,
                SPACE_ID,
                case["question"],
                timeout_seconds=TIMEOUT_SECONDS,
            )
        except Exception as exc:  # network/timeout/etc.
            attempts.append({
                "attempt": attempt_idx,
                "error": f"{type(exc).__name__}: {exc}",
                "genie_sql": None,
                "row_count": 0,
                "result_preview_records": [],
                "check_result": None,
            })
            continue

        df = response["df"]
        if df is None:
            attempts.append({
                "attempt": attempt_idx,
                "error": "Genie returned no data (status=%s, text=%s)"
                         % (response["status"], (response["text"] or "")[:200]),
                "genie_sql": response["sql"],
                "row_count": 0,
                "result_preview_records": [],
                "check_result": None,
            })
            continue

        check_result = case["check_fn"](df, gt)
        preview = df.head(10).to_dict(orient="records")
        # Coerce numpy/pandas types to JSON-friendly
        preview = json.loads(json.dumps(preview, default=str))

        attempts.append({
            "attempt": attempt_idx,
            "error": None,
            "genie_sql": response["sql"],
            "row_count": int(len(df)),
            "result_preview_records": preview,
            "check_result": {k: (float(v) if hasattr(v, "item") else v)
                             for k, v in check_result.items()},
        })

        if check_result.get("passed"):
            passed = True
            metric_value = check_result.get(case["metric_key"])
            break
        metric_value = check_result.get(case["metric_key"])

    return {
        "name": case["name"],
        "question": case["question"],
        "passed": passed,
        "metric_key": case["metric_key"],
        "metric_value": metric_value,
        "attempts_made": len(attempts),
        "attempts": attempts,
    }


def _format_metric(value) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _print_report(results: list[dict], run_meta: dict) -> None:
    print("=" * 60)
    print(f"Genie test run — {run_meta['timestamp_utc']}")
    print(f"Space: {run_meta['space_id']}")
    print("=" * 60)

    name_width = max(len(r["name"]) for r in results)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        metric = f"{r['metric_key']}={_format_metric(r['metric_value'])}"
        attempt = f"attempt={r['attempts_made']}/{RETRIES}"
        print(f"  {r['name']:<{name_width}}  {status}   {metric:<32} {attempt}")

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    print("-" * 60)
    print(f"PASSED: {passed}   FAILED: {failed}")


def _write_artifact(results: list[dict], run_meta: dict) -> str:
    """Write the full run record as JSON to the results volume.

    Uses the Files API (via WorkspaceClient) so the path works for any
    Volume the user's Databricks identity can write to.
    """
    filename = (
        "genie_test_"
        + run_meta["timestamp_utc"].replace(":", "-").replace(".", "-")
        + ".json"
    )
    remote_path = f"{RESULTS_VOLUME_DIR}/{filename}"
    payload = {
        "timestamp_utc": run_meta["timestamp_utc"],
        "space_id": run_meta["space_id"],
        "retries": RETRIES,
        "summary": {
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"]),
        },
        "cases": results,
    }
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")

    w = WorkspaceClient()
    import io
    # Files API accepts a file-like object and supports /Volumes/... paths.
    w.files.upload(file_path=remote_path, contents=io.BytesIO(body), overwrite=True)
    return remote_path


def main() -> int:
    gt = load_ground_truth(GROUND_TRUTH_PATH)
    w = WorkspaceClient()

    run_meta = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space_id": SPACE_ID,
    }

    results = [_run_case(w, case, gt) for case in TEST_CASES]

    _print_report(results, run_meta)

    artifact_path = _write_artifact(results, run_meta)
    print(f"Artifact: {artifact_path}")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
