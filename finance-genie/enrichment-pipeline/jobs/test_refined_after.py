"""Refined-after validation runner — checks whether the BEFORE answers hold under enrichment.

Runs two pairs drawn from demo-guide/flow.md § "Refined After". The BEFORE question is the
original query asked against the Silver-only space; the AFTER question is the follow-up asked
against the enriched Gold space to validate (or invalidate) the BEFORE interpretation.

Pair 1 — High-volume account community membership
  BEFORE: for the top 20 accounts by volume, how many unique merchants did each visit?
  AFTER:  for those same top-20 accounts, what is their community membership and risk tier —
          are they concentrated in a small number of communities or spread across the book?

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID_BEFORE      — required; BEFORE space (Silver-only)
  GENIE_SPACE_ID_AFTER       — required; AFTER space (enriched Gold)
  RESULTS_VOLUME_DIR         — required; UC Volume path for the Markdown log
  GENIE_TEST_RETRIES         — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage:
    python -m cli submit test_refined_after.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import traceback
from datetime import datetime, timezone

from _cluster_bootstrap import inject_params, resolve_here

inject_params()
_HERE = resolve_here()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _demo_utils import ask_genie  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

SPACE_ID_BEFORE = os.environ["GENIE_SPACE_ID_BEFORE"]
SPACE_ID_AFTER = os.environ["GENIE_SPACE_ID_AFTER"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")
RETRIES = int(os.environ.get("GENIE_TEST_RETRIES", "2"))
TIMEOUT_SECONDS = int(os.environ.get("GENIE_TEST_TIMEOUT_SECONDS", "120"))

PREVIEW_ROWS = 5


PAIRS = [
    {
        "title": "High-volume account community membership",
        "before": (
            "For the top 20 accounts by total transaction volume, how many unique merchants "
            "did each account visit?"
        ),
        "after": (
            "For accounts in the top 20 by total transaction volume, what is their community "
            "membership status and risk tier? Are those accounts concentrated in a small number "
            "of communities, or are they spread across the book?"
        ),
    },
]


def _run_case(w: WorkspaceClient, space_id: str, question: str) -> dict:
    last_error = None
    for _ in range(RETRIES):
        try:
            response = ask_genie(w, space_id, question, timeout_seconds=TIMEOUT_SECONDS)
            df = response["df"]
            row_count = int(len(df)) if df is not None else 0
            preview = (
                json.loads(json.dumps(df.head(PREVIEW_ROWS).to_dict(orient="records"), default=str))
                if df is not None else []
            )
            return {
                "error": None,
                "sql": response.get("sql") or "",
                "text": response.get("text") or "",
                "row_count": row_count,
                "preview": preview,
            }
        except Exception as exc:
            print(traceback.format_exc(), file=sys.stderr)
            last_error = f"{type(exc).__name__}: {exc}"
    return {
        "error": last_error or "unknown error",
        "sql": "",
        "text": "",
        "row_count": 0,
        "preview": [],
    }


def _render_side(label: str, question: str, result: dict) -> list[str]:
    lines = [f"### {label}", "", f"**Question:** {question}", ""]
    if result["error"]:
        lines.extend([f"**Error:** `{result['error']}`", ""])
        return lines
    lines.extend([f"**Rows returned:** {result['row_count']}", ""])
    if result["sql"]:
        lines.extend(["**SQL:**", "", "```sql", result["sql"].strip(), "```", ""])
    if result["text"]:
        lines.extend([f"**Summary:** {result['text'].strip()}", ""])
    if result["preview"]:
        shown = min(PREVIEW_ROWS, result["row_count"])
        lines.extend([
            f"**Preview (first {shown} of {result['row_count']} rows):**",
            "",
            "```json",
            json.dumps(result["preview"], indent=2, default=str),
            "```",
            "",
        ])
    return lines


def _render_log(pairs_with_results: list[dict], run_meta: dict) -> str:
    lines = [
        f"# Refined-after validation review — {run_meta['timestamp_utc']}",
        "",
        f"- BEFORE space: `{run_meta['space_id_before']}`",
        f"- AFTER space: `{run_meta['space_id_after']}`",
        f"- Pairs: {len(pairs_with_results)}",
        "",
        "Each section pairs the original BEFORE question (Silver-only space) with a "
        "validation AFTER question (enriched Gold space). The goal is not to show a gap — "
        "it is to check whether the BEFORE interpretation holds or collapses once community "
        "membership and risk tier are available as dimensions.",
        "",
    ]
    for idx, item in enumerate(pairs_with_results, start=1):
        pair = item["pair"]
        lines.extend([f"## {idx}. {pair['title']}", ""])
        lines.extend(_render_side("BEFORE", pair["before"], item["before_result"]))
        lines.extend(_render_side("AFTER (validation)", pair["after"], item["after_result"]))
        lines.extend(["---", ""])
    return "\n".join(lines)


def main() -> int:
    w = WorkspaceClient()
    run_meta = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space_id_before": SPACE_ID_BEFORE,
        "space_id_after": SPACE_ID_AFTER,
    }

    pairs_with_results = []
    for idx, pair in enumerate(PAIRS, start=1):
        print(f"[{idx}/{len(PAIRS)}] {pair['title']}")
        print(f"  BEFORE -> {SPACE_ID_BEFORE}")
        before_result = _run_case(w, SPACE_ID_BEFORE, pair["before"])
        print(f"    rows={before_result['row_count']} error={before_result['error']}")
        print(f"  AFTER  -> {SPACE_ID_AFTER}")
        after_result = _run_case(w, SPACE_ID_AFTER, pair["after"])
        print(f"    rows={after_result['row_count']} error={after_result['error']}")
        pairs_with_results.append({
            "pair": pair,
            "before_result": before_result,
            "after_result": after_result,
        })

    markdown = _render_log(pairs_with_results, run_meta)
    print()
    print(markdown)

    ts_safe = run_meta["timestamp_utc"].replace(":", "-")
    remote_path = f"{RESULTS_VOLUME_DIR}/refined_after_validation_{ts_safe}.md"
    w.files.upload(
        file_path=remote_path,
        contents=io.BytesIO(markdown.encode("utf-8")),
        overwrite=True,
    )
    print(f"\nLog written: {remote_path}")
    return 0


if __name__ == "__main__":
    main()
