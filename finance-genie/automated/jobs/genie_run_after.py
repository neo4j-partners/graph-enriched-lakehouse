"""AFTER space runner — asks analyst-style questions against the enriched Genie Space.

Loads five category sampler modules (one per question category), randomly picks
one question from each, asks all selected questions to Genie, and captures the
responses (SQL, rows, summary text) as an artifact. No grading is performed;
grading lands in Phase 5 once the captured responses stabilize.

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID_AFTER       — required; the AFTER space to query
  RESULTS_VOLUME_DIR         — required; UC Volume path for artifact output
  SAMPLERS                   — optional; comma-separated category module names
                               (e.g. "cat1_portfolio,cat3_community_rollup");
                               defaults to all five categories
  GENIE_TEST_RETRIES         — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage:
    python -m cli submit genie_run_after.py
    python -m cli submit genie_run_after.py SAMPLERS=cat1_portfolio,cat4_operational
"""

from __future__ import annotations

import importlib
import io
import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone

from _cluster_bootstrap import inject_params, resolve_here

inject_params()
_HERE = resolve_here()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from demo_utils import ask_genie  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402
from genie_run_artifact import sql_preview, wrap_text  # noqa: E402

SPACE_ID = os.environ["GENIE_SPACE_ID_AFTER"]
LABEL = "after"
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")
RETRIES = int(os.environ.get("GENIE_TEST_RETRIES", "2"))
TIMEOUT_SECONDS = int(os.environ.get("GENIE_TEST_TIMEOUT_SECONDS", "120"))

_ALL_SAMPLERS = [
    "cat1_portfolio",
    "cat2_cohort",
    "cat3_community_rollup",
    "cat4_operational",
    "cat5_merchant",
]

_SAMPLER_LABELS = {
    "cat1_portfolio": "Portfolio composition",
    "cat2_cohort": "Cohort comparisons",
    "cat3_community_rollup": "Community rollups",
    "cat4_operational": "Operational workload",
    "cat5_merchant": "Merchant-side",
}


def _resolve_samplers() -> list[str]:
    raw = os.environ.get("SAMPLERS", "").strip()
    if not raw:
        return list(_ALL_SAMPLERS)
    names = [s.strip() for s in raw.split(",") if s.strip()]
    unknown = [n for n in names if n not in _ALL_SAMPLERS]
    if unknown:
        raise ValueError(f"Unknown sampler(s): {unknown}. Valid: {_ALL_SAMPLERS}")
    return names


def _pick_question(sampler_name: str) -> dict:
    module = importlib.import_module(sampler_name)
    return random.choice(module.QUESTIONS)


def _run_case(w: WorkspaceClient, question_def: dict) -> dict:
    attempts: list[dict] = []

    for attempt_idx in range(1, RETRIES + 1):
        try:
            response = ask_genie(w, SPACE_ID, question_def["question"], timeout_seconds=TIMEOUT_SECONDS)
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
        row_count = int(len(df)) if df is not None else 0
        preview = (
            json.loads(json.dumps(df.head(10).to_dict(orient="records"), default=str))
            if df is not None else []
        )

        attempts.append({
            "attempt": attempt_idx,
            "error": None,
            "genie_sql": response["sql"],
            "genie_response_text": response["text"],
            "row_count": row_count,
            "result_preview_records": preview,
            "metric": None,
        })
        break

    last = attempts[-1] if attempts else {}
    responded = last.get("error") is None and last.get("row_count", 0) > 0

    return {
        "name": question_def["name"],
        "question": question_def["question"],
        "responded": responded,
        "attempts_made": len(attempts),
        "attempts": attempts,
        "metric": None,
    }


def _status(result: dict) -> str:
    if not result["attempts"]:
        return "ERROR"
    last = result["attempts"][-1]
    if last.get("error"):
        return "NO DATA" if "no data" in (last.get("error") or "").lower() else "ERROR"
    return "RESPONDED"


def _print_report(results: list[dict], sampler_names: list[str], run_meta: dict) -> None:
    print("=" * 78)
    print(f"Genie AFTER run — {run_meta['timestamp_utc']}")
    print(f"Space: {run_meta['space_id']}")
    print(f"Categories: {', '.join(_SAMPLER_LABELS.get(s, s) for s in sampler_names)}")
    print("Purpose: capture analyst-style responses over enriched catalog (no grading)")
    print("=" * 78)

    for idx, r in enumerate(results, start=1):
        last = r["attempts"][-1] if r["attempts"] else {}
        rows = int(last.get("row_count") or 0)

        print()
        print(f"[{idx}] {r['name']} — {_status(r)}")
        print(f"    Question: {wrap_text(r['question'])}")
        print(f"    Rows:     {rows}")
        print(f"    SQL:      {sql_preview(r)}")

        text = (last.get("genie_response_text") or "").strip()
        if text:
            print(f"    Summary:  {wrap_text(text[:200])}")

        if not r["responded"] and last.get("error"):
            print(f"    Error:    {(last['error'] or '')[:200]}")

    responded = sum(1 for r in results if r["responded"])
    print()
    print("-" * 78)
    print(f"Responded: {responded}/{len(results)}")
    print(
        "Summary: AFTER catalog answered the above analyst questions using community, "
        "risk-tier, and similarity dimensions unlocked by GDS enrichment."
    )


def _write_artifact(w: WorkspaceClient, results: list[dict], run_meta: dict) -> str:
    ts_safe = run_meta["timestamp_utc"].replace(":", "-").replace(".", "-")
    remote_path = f"{RESULTS_VOLUME_DIR}/genie_run_after_{ts_safe}.json"

    payload = {
        "space_id": run_meta["space_id"],
        "label": LABEL,
        "timestamp_utc": run_meta["timestamp_utc"],
        "gate_enabled": False,
        "retries_configured": RETRIES,
        "summary": {
            "responded": sum(1 for r in results if r["responded"]),
            "total": len(results),
            "meets_after_gate": 0,
        },
        "cases": results,
    }
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    w.files.upload(file_path=remote_path, contents=io.BytesIO(body), overwrite=True)
    return remote_path


def main() -> int:
    sampler_names = _resolve_samplers()
    w = WorkspaceClient()

    run_meta = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space_id": SPACE_ID,
    }

    questions = []
    for sampler_name in sampler_names:
        q = _pick_question(sampler_name)
        questions.append(q)
        print(f"Selected from {sampler_name}: {q['name']}")

    results = [_run_case(w, q) for q in questions]
    _print_report(results, sampler_names, run_meta)

    artifact_path = _write_artifact(w, results, run_meta)
    print(f"\nArtifact: {artifact_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
