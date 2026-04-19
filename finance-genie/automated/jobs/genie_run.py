"""Parameterized Genie Space runner — replaces genie_test.py + genie_test_before.py.

Runs three analyst-phrased questions against any Genie Space passed via
GENIE_SPACE_ID, computes the after-GDS metrics for observation, and writes
a full JSON artifact to the UC Volume. No pass/fail gating by default.

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID           — required; the space to query
  LABEL                    — optional; human label for this run (e.g. "before" / "after")
                             falls back to space_id[:8] if unset
  GATE                     — optional; "true" to exit non-zero when any after-gate
                             criterion is not met (reproduces legacy genie_test.py
                             behavior); default "false"
  GROUND_TRUTH_PATH        — required; path to ground_truth.json on the UC Volume
  RESULTS_VOLUME_DIR       — required; UC Volume path for artifact output
  GENIE_TEST_RETRIES       — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage (from finance-genie/automated/ with .env in place):
    python -m cli upload --all
    python -m cli submit genie_run.py GENIE_SPACE_ID=$GENIE_SPACE_ID_BEFORE LABEL=before
    python -m cli submit genie_run.py GENIE_SPACE_ID=$GENIE_SPACE_ID_AFTER LABEL=after
    python -m cli submit genie_run.py GENIE_SPACE_ID=$GENIE_SPACE_ID_AFTER LABEL=after GATE=true
"""

from __future__ import annotations

import io
import json
import os
import sys
import textwrap
import traceback
from datetime import datetime, timezone
from pathlib import Path

from _cluster_bootstrap import inject_params, resolve_here

# --------------------------------------------------------------------------- #
# 1. Bootstrap: inject .env vars from KEY=VALUE argv, resolve script directory #
# --------------------------------------------------------------------------- #
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

# --------------------------------------------------------------------------- #
# 2. Config                                                                   #
# --------------------------------------------------------------------------- #
SPACE_ID = os.environ["GENIE_SPACE_ID"]
LABEL = os.environ.get("LABEL") or SPACE_ID[:8]
GATE = os.environ.get("GATE", "false").strip().lower() == "true"
GROUND_TRUTH_PATH = os.environ["GROUND_TRUTH_PATH"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")
RETRIES = int(os.environ.get("GENIE_TEST_RETRIES", "2"))
TIMEOUT_SECONDS = int(os.environ.get("GENIE_TEST_TIMEOUT_SECONDS", "120"))

# --------------------------------------------------------------------------- #
# 3. Question set — analyst-phrased BEFORE set, run against both spaces       #
#    so both receive a fair question and the metric delta is apples-to-apples.#
# --------------------------------------------------------------------------- #

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


def _community_check(df, gt):
    rings_as_lists = [r["account_ids"] for r in gt["rings"]]
    return check_community_purity(df, rings_as_lists, ring_community_map=_load_ring_community_map())


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


TEST_CASES = [
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
        "question": (
            "Find groups of accounts transferring money heavily among themselves."
        ),
        "check_fn": _community_check,
        "metric_key": "max_ring_coverage",
        "after_gate_criterion": "> 0.80",
    },
    {
        "name": "merchant_overlap",
        "question": (
            "Which pairs of accounts have visited the most merchants in common?"
        ),
        "check_fn": _merchant_check,
        "metric_key": "same_ring_fraction",
        "after_gate_criterion": "> 0.60 with >=5 pairs",
    },
]

# --------------------------------------------------------------------------- #
# 4. Per-question runner                                                       #
# --------------------------------------------------------------------------- #

def _run_case(w: WorkspaceClient, case: dict, gt: dict) -> dict:
    attempts: list[dict] = []
    final_metric: dict | None = None

    for attempt_idx in range(1, RETRIES + 1):
        try:
            response = ask_genie(
                w,
                SPACE_ID,
                case["question"],
                timeout_seconds=TIMEOUT_SECONDS,
            )
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
        if df is None:
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

        check_result = case["check_fn"](df, gt)
        preview = df.head(10).to_dict(orient="records")
        preview = json.loads(json.dumps(preview, default=str))

        metric_value = check_result.get(case["metric_key"])
        if metric_value is not None and hasattr(metric_value, "item"):
            metric_value = metric_value.item()

        detail = {k: (v.item() if hasattr(v, "item") else v) for k, v in check_result.items()}

        metric = {
            "key": case["metric_key"],
            "value": float(metric_value) if metric_value is not None else None,
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
            "row_count": int(len(df)),
            "result_preview_records": preview,
            "metric": metric,
        })
        break  # first successful Genie response ends retries

    last = attempts[-1] if attempts else {}
    responded = last.get("error") is None and last.get("row_count", 0) > 0

    return {
        "name": case["name"],
        "question": case["question"],
        "responded": responded,
        "attempts_made": len(attempts),
        "attempts": attempts,
        "metric": final_metric,
    }


# --------------------------------------------------------------------------- #
# 5. Report printer                                                            #
# --------------------------------------------------------------------------- #

_VERDICT_LABELS = {
    "hub_detection":        ("FRAUD DETECTED",       "NO FRAUD FOUND"),
    "community_structure":  ("FRAUD RINGS DETECTED", "NO RINGS FOUND"),
    "merchant_overlap":     ("COLLUSION DETECTED",   "NO COLLUSION FOUND"),
}


def _verdict(result: dict) -> str:
    if not result["attempts"]:
        return "ERROR"
    if not result["responded"]:
        last_err = (result["attempts"][-1].get("error") or "")
        return "NO DATA" if "no data" in last_err.lower() else "ERROR"
    passed = (result["metric"] or {}).get("meets_after_gate")
    yes, no = _VERDICT_LABELS.get(result["name"], ("RESPONDED", "NO SIGNAL"))
    return yes if passed else no


def _findings(name: str, detail: dict | None) -> list[str]:
    if not detail:
        return []
    if name == "hub_detection":
        tp = int(detail.get("true_positives", 0))
        n = int(detail.get("topn", 0))
        return [
            f"{tp}/{n} of the top-{n} risk-scored accounts are known fraud ring members",
            "Precision = share of returned hubs that are ground-truth fraud accounts",
        ]
    if name == "community_structure":
        cov = float(detail.get("max_ring_coverage", 0.0))
        groups = int(detail.get("groups_returned", 0))
        rows = int(detail.get("total_rows", 0))
        stype = detail.get("structure_type", "")
        return [
            f"{groups} community group(s) returned across {rows} rows (shape: {stype})",
            f"Max ring coverage {cov:.0%} = the best community covered this share of a real fraud ring",
        ]
    if name == "merchant_overlap":
        same = int(detail.get("same_ring_pairs", 0))
        cross = int(detail.get("cross_ring_pairs", 0))
        unk = int(detail.get("unknown_pairs", 0))
        total = int(detail.get("total_pairs", 0))
        touched = int(detail.get("rings_touched", 0))
        return [
            f"{same}/{total} top-similarity pairs are same-ring; {cross} cross-ring; {unk} unknown",
            f"Same-ring pairs span {touched} distinct fraud ring(s)",
            "Same-ring fraction = share of returned pairs where both accounts share a ground-truth ring",
        ]
    return []


def _sql_preview(result: dict, max_chars: int = 220) -> str:
    if not result["attempts"]:
        return "(no SQL)"
    sql = (result["attempts"][-1].get("genie_sql") or "").strip()
    if not sql:
        return "(no SQL)"
    single_line = " ".join(sql.split())
    if len(single_line) > max_chars:
        return single_line[:max_chars] + "…"
    return single_line


def _wrap_with_indent(text: str, indent: int = 14, width: int = 78) -> str:
    pad = " " * indent
    wrapped = textwrap.wrap(text, width=max(width - indent, 20)) or [text]
    return ("\n" + pad).join(wrapped)


def _final_verdict(results: list[dict]) -> str:
    total = len(results)
    responded = sum(1 for r in results if r["responded"])
    detected = sum(
        1 for r in results
        if r["responded"] and (r["metric"] or {}).get("meets_after_gate")
    )
    if detected == total:
        return f"Fraud signal detected in {detected}/{total} tests — Genie surfaced hubs, rings, and collusion."
    if detected == 0 and responded == total:
        return f"No fraud signal detected — all {total} questions responded but none met the after-GDS criterion."
    if detected == 0:
        return f"No fraud signal detected — only {responded}/{total} questions produced usable data."
    return f"Partial fraud signal — detected {detected}/{total} patterns; {total - detected} question(s) missed criterion."


def _print_report(results: list[dict], run_meta: dict) -> None:
    print("=" * 78)
    print(f"Genie run — {run_meta['timestamp_utc']}")
    print(f"Space: {run_meta['space_id']}  Label: {run_meta['label']}")
    gate_note = "GATE=true (exits non-zero on threshold miss)" if GATE else "GATE=false (observation only)"
    print(gate_note)
    print("=" * 78)

    for idx, r in enumerate(results, start=1):
        verdict = _verdict(r)
        m = r["metric"]
        rows = int(r["attempts"][-1].get("row_count") or 0) if r["attempts"] else 0

        print()
        print(f"[{idx}] {r['name']} — {verdict}")
        print(f"    Question: {_wrap_with_indent(r['question'])}")

        if m and m.get("value") is not None:
            print(f"    Metric:   {m['key']}={float(m['value']):.2f}  (criterion {m['after_gate_criterion']})")
        else:
            print(f"    Metric:   n/a  (criterion {(m or {}).get('after_gate_criterion', 'n/a')})")

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
        print(f"    SQL:      {_sql_preview(r)}")

    responded = sum(1 for r in results if r["responded"])
    print()
    print("-" * 78)
    print(f"Responded: {responded}/{len(results)}")
    print(f"Verdict:   {_final_verdict(results)}")


# --------------------------------------------------------------------------- #
# 6. Artifact writer                                                           #
# --------------------------------------------------------------------------- #

def _write_artifact(
    w: WorkspaceClient, results: list[dict], run_meta: dict
) -> tuple[str, dict]:
    ts_safe = run_meta["timestamp_utc"].replace(":", "-").replace(".", "-")
    filename = f"genie_run_{LABEL}_{ts_safe}.json"
    remote_path = f"{RESULTS_VOLUME_DIR}/{filename}"

    payload = {
        "space_id": run_meta["space_id"],
        "label": run_meta["label"],
        "timestamp_utc": run_meta["timestamp_utc"],
        "gate_enabled": run_meta["gate_enabled"],
        "retries_configured": RETRIES,
        "summary": {
            "responded": sum(1 for r in results if r["responded"]),
            "total": len(results),
            "meets_after_gate": sum(
                1 for r in results if (r["metric"] or {}).get("meets_after_gate")
            ),
        },
        "cases": results,
    }
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    w.files.upload(file_path=remote_path, contents=io.BytesIO(body), overwrite=True)
    # Round-trip through JSON so the returned dict matches what a downstream
    # load_run_artifact() read would produce (e.g. tuples become lists).
    return remote_path, json.loads(body)


# --------------------------------------------------------------------------- #
# 7. Main                                                                     #
# --------------------------------------------------------------------------- #

def run() -> tuple[int, str, dict]:
    """Execute the Genie run and return (exit_code, artifact_remote_path, artifact_dict).

    The in-memory artifact dict matches the JSON written to the UC Volume and is
    returned so callers (e.g. genie_run_after.py's comparison fold) can reuse it
    without re-reading the Volume.
    """
    gt = load_ground_truth(GROUND_TRUTH_PATH)
    w = WorkspaceClient()

    run_meta = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space_id": SPACE_ID,
        "label": LABEL,
        "gate_enabled": GATE,
    }

    results = [_run_case(w, case, gt) for case in TEST_CASES]

    _print_report(results, run_meta)

    artifact_path, artifact = _write_artifact(w, results, run_meta)
    print(f"\nArtifact: {artifact_path}")

    if GATE:
        failed = [r for r in results if not (r["metric"] or {}).get("meets_after_gate")]
        if failed:
            print(f"\nGATE FAIL — {len(failed)} case(s) did not meet after-gate criterion:")
            for r in failed:
                print(f"  {r['name']}")
            return 1, artifact_path, artifact

    return 0, artifact_path, artifact


def main() -> int:
    exit_code, _, _ = run()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
