"""BEFORE space runner — asks structural-discovery questions against the base-table Genie Space.

Confirms the gap that the BEFORE catalog cannot close: structural questions that
require network topology do not resolve from row-level SQL alone. Each miss is
reported as evidence of the gap, not as a test failure.

A teaser question drawn from the AFTER category set is appended. Asked against
the BEFORE catalog it cannot land cleanly; it is reported as
"NOT AVAILABLE ON THIS CATALOG — answered in AFTER run."

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID_BEFORE      — required; the BEFORE space to query
  GROUND_TRUTH_PATH          — required; path to ground_truth.json on the UC Volume
  RESULTS_VOLUME_DIR         — required; UC Volume path for artifact output
  GENIE_TEST_RETRIES         — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage:
    python -m cli submit genie_run_before.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from _cluster_bootstrap import inject_params, resolve_here

inject_params()
_HERE = resolve_here()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from demo_utils import (  # noqa: E402
    ask_genie,
    check_community_purity,
    check_ring_pair_fraction,
    check_risk_score_precision,
    load_ground_truth,
)
from databricks.sdk import WorkspaceClient  # noqa: E402
from genie_run_artifact import sql_preview, wrap_text  # noqa: E402

SPACE_ID = os.environ["GENIE_SPACE_ID_BEFORE"]
LABEL = "before"
GROUND_TRUTH_PATH = os.environ["GROUND_TRUTH_PATH"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")
RETRIES = int(os.environ.get("GENIE_TEST_RETRIES", "2"))
TIMEOUT_SECONDS = int(os.environ.get("GENIE_TEST_TIMEOUT_SECONDS", "120"))

_SCOPE_FOOTER = (
    "Synthetic dataset. Structural-signal ratios are theoretically scale-invariant;\n"
    "absolute precision numbers reflect the teaching dataset. See SCOPING_GUIDE.md\n"
    "for production-scale guidance."
)


def _hub_check(df, gt):
    return check_risk_score_precision(df, gt, topn=20)


def _load_ring_community_map() -> "dict[str, list[int]] | None":
    try:
        map_path = str(Path(GROUND_TRUTH_PATH).parent / "ring_community_map.json")
        with open(map_path) as f:
            data = json.load(f)
        return {k: [int(x) for x in v] for k, v in data["ring_community_map"].items()}
    except (FileNotFoundError, KeyError):
        return None


def _make_community_check(ring_community_map):
    def _community_check(df, gt):
        rings_as_lists = [r["account_ids"] for r in gt["rings"]]
        return check_community_purity(df, rings_as_lists, ring_community_map=ring_community_map)
    return _community_check


def _merchant_check(df, gt):
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
            "error": f"expected two account columns, got {list(df.columns)}",
        }
    a_col, b_col = account_cols[0], account_cols[1]
    pairs = list(zip(df[a_col].astype(int), df[b_col].astype(int)))
    rings_as_lists = [r["account_ids"] for r in gt["rings"]]
    return check_ring_pair_fraction(pairs, rings_as_lists)


def _build_cases(ring_community_map) -> list[dict]:
    return [
        {
            "name": "hub_detection",
            "question": (
                "Are there accounts that seem to be the hub of a money movement "
                "network that are potentially fraudulent?"
            ),
            "check_fn": _hub_check,
            "metric_key": "precision",
            "after_gate_criterion": "> 0.70",
        },
        {
            "name": "community_structure",
            "question": "Find groups of accounts transferring money heavily among themselves.",
            "check_fn": _make_community_check(ring_community_map),
            "metric_key": "max_ring_coverage",
            "after_gate_criterion": "> 0.80",
        },
        {
            "name": "merchant_overlap",
            "question": "Which pairs of accounts have visited the most merchants in common?",
            "check_fn": _merchant_check,
            "metric_key": "same_ring_fraction",
            "after_gate_criterion": "> 0.60 with >=5 pairs",
        },
        {
            "name": "teaser_portfolio",
            "question": (
                "What share of accounts sits in communities flagged as ring candidates, "
                "broken out by region?"
            ),
        },
    ]


def _run_case(w: WorkspaceClient, case: dict, gt: dict) -> dict:
    """Run one question. Skips grading when the case has no check_fn (teaser)."""
    attempts: list[dict] = []
    final_metric: dict | None = None
    check_fn = case.get("check_fn")
    is_teaser = check_fn is None

    for attempt_idx in range(1, RETRIES + 1):
        try:
            response = ask_genie(w, SPACE_ID, case["question"], timeout_seconds=TIMEOUT_SECONDS)
        except Exception as exc:
            tb = traceback.format_exc()
            print(tb, file=sys.stderr)
            attempts.append({
                "attempt": attempt_idx,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": tb,
                "genie_sql": None,
                "genie_response_text": None,
                "row_count": 0,
                "result_preview_records": [],
                "metric": None,
            })
            continue

        df = response["df"]
        if df is None and not is_teaser:
            attempts.append({
                "attempt": attempt_idx,
                "error": f"Genie returned no data (status={response['status']}, text={(response['text'] or '')[:200]})",
                "genie_sql": response["sql"],
                "genie_response_text": response["text"],
                "row_count": 0,
                "result_preview_records": [],
                "metric": None,
            })
            continue

        row_count = int(len(df)) if df is not None else 0
        preview = (
            json.loads(json.dumps(df.head(10).to_dict(orient="records"), default=str))
            if df is not None else []
        )

        metric = None
        if check_fn is not None and df is not None:
            check_result = check_fn(df, gt)
            metric_val = check_result.get(case["metric_key"])
            if metric_val is not None and hasattr(metric_val, "item"):
                metric_val = metric_val.item()
            detail = {k: (v.item() if hasattr(v, "item") else v) for k, v in check_result.items()}
            metric = {
                "key": case["metric_key"],
                "value": float(metric_val) if metric_val is not None else None,
                "after_gate_criterion": case["after_gate_criterion"],
                "meets_after_gate": bool(check_result.get("passed", False)),
                "detail": detail,
            }
            final_metric = metric

        attempts.append({
            "attempt": attempt_idx,
            "error": None,
            "genie_sql": response["sql"],
            "genie_response_text": response["text"],
            "row_count": row_count,
            "result_preview_records": preview,
            "metric": metric,
        })
        break

    last = attempts[-1] if attempts else {}
    if is_teaser:
        responded = last.get("error") is None
    else:
        responded = last.get("error") is None and last.get("row_count", 0) > 0

    return {
        "name": case["name"],
        "question": case["question"],
        "responded": responded,
        "attempts_made": len(attempts),
        "attempts": attempts,
        "metric": final_metric,
    }


def _verdict(result: dict) -> str:
    if not result["attempts"]:
        return "ERROR"
    last = result["attempts"][-1]
    if last.get("error"):
        return "NO DATA" if "no data" in (last.get("error") or "").lower() else "ERROR"
    passed = (result["metric"] or {}).get("meets_after_gate")
    return "UNEXPECTED SIGNAL FOUND" if passed else "STRUCTURAL GAP CONFIRMED"


def _findings(name: str, detail: dict | None) -> list[str]:
    if not detail:
        return []
    if name == "hub_detection":
        tp = int(detail.get("true_positives", 0))
        n = int(detail.get("topn", 0))
        return [
            f"{tp}/{n} top-{n} risk-scored accounts are known fraud ring members",
            "Precision = share of returned hubs that are ground-truth fraud accounts",
        ]
    if name == "community_structure":
        cov = float(detail.get("max_ring_coverage", 0.0))
        groups = int(detail.get("groups_returned", 0))
        rows = int(detail.get("total_rows", 0))
        stype = detail.get("structure_type", "")
        return [
            f"{groups} community group(s) returned across {rows} rows (shape: {stype})",
            f"Max ring coverage {cov:.0%} — best community covered this share of a real fraud ring",
        ]
    if name == "merchant_overlap":
        same = int(detail.get("same_ring_pairs", 0))
        total = int(detail.get("total_pairs", 0))
        touched = int(detail.get("rings_touched", 0))
        return [
            f"{same}/{total} top-similarity pairs are same-ring; spans {touched} distinct fraud ring(s)",
            "Same-ring fraction = share of returned pairs where both accounts share a ground-truth ring",
        ]
    return []


def _print_report(results: list[dict], run_meta: dict) -> None:
    structural = [r for r in results if r["name"] != "teaser_portfolio"]
    teaser = next((r for r in results if r["name"] == "teaser_portfolio"), None)

    print("=" * 78)
    print(f"Genie BEFORE run — {run_meta['timestamp_utc']}")
    print(f"Space: {run_meta['space_id']}")
    print("Purpose: confirm structural gap on base tables (misses are expected evidence)")
    print("=" * 78)

    for idx, r in enumerate(structural, start=1):
        verdict = _verdict(r)
        m = r["metric"]
        rows = int(r["attempts"][-1].get("row_count") or 0) if r["attempts"] else 0

        print()
        print(f"[{idx}] {r['name']} — {verdict}")
        print(f"    Question: {wrap_text(r['question'])}")

        if m and m.get("value") is not None:
            print(f"    Metric:   {m['key']}={float(m['value']):.2f}  (after-GDS criterion: {m['after_gate_criterion']})")
        else:
            print(f"    Metric:   n/a")

        findings = _findings(r["name"], (m or {}).get("detail"))
        if findings:
            print(f"    Finding:  {findings[0]}")
            for line in findings[1:]:
                print(f"              {line}")
        elif not r["responded"] and r["attempts"]:
            err = (r["attempts"][-1].get("error") or "").strip()
            if err:
                print(f"    Error:    {err[:200]}")

        print(f"    Rows:     {rows}")
        print(f"    SQL:      {sql_preview(r)}")

    if teaser:
        rows = int(teaser["attempts"][-1].get("row_count") or 0) if teaser["attempts"] else 0
        print()
        print(f"[T] {teaser['name']} — NOT AVAILABLE ON THIS CATALOG — answered in AFTER run")
        print(f"    Question: {wrap_text(teaser['question'])}")
        print(f"    Note:     community_id and is_ring_community columns do not exist in base tables.")
        print(f"    Rows:     {rows}")
        print(f"    SQL:      {sql_preview(teaser)}")

    confirmed = sum(
        1 for r in structural
        if r["responded"] and not (r["metric"] or {}).get("meets_after_gate")
    )
    print()
    print("-" * 78)
    print(f"Structural gap confirmed in {confirmed}/{len(structural)} questions.")
    print(
        "Summary: BEFORE catalog cannot resolve structural questions from row-level SQL. "
        "Enrichment unlocks portfolio, cohort, community, operational, and merchant-composition "
        "queries in the AFTER run."
    )
    print()
    print(_SCOPE_FOOTER)


def _write_artifact(w: WorkspaceClient, results: list[dict], run_meta: dict) -> str:
    ts_safe = run_meta["timestamp_utc"].replace(":", "-").replace(".", "-")
    remote_path = f"{RESULTS_VOLUME_DIR}/genie_run_before_{ts_safe}.json"

    payload = {
        "space_id": run_meta["space_id"],
        "label": LABEL,
        "timestamp_utc": run_meta["timestamp_utc"],
        "gate_enabled": False,
        "retries_configured": RETRIES,
        "summary": {
            "responded": sum(1 for c in results if c["responded"]),
            "total": len(results),
            "meets_after_gate": sum(
                1 for c in results if (c["metric"] or {}).get("meets_after_gate")
            ),
        },
        "cases": results,
    }
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    w.files.upload(file_path=remote_path, contents=io.BytesIO(body), overwrite=True)
    return remote_path


def main() -> int:
    gt = load_ground_truth(GROUND_TRUTH_PATH)
    ring_community_map = _load_ring_community_map()
    cases = _build_cases(ring_community_map)
    w = WorkspaceClient()

    run_meta = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space_id": SPACE_ID,
    }

    results = [_run_case(w, case, gt) for case in cases]
    _print_report(results, run_meta)

    artifact_path = _write_artifact(w, results, run_meta)
    print(f"\nArtifact: {artifact_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
