"""Anchor-pair BEFORE/AFTER runner — captures paired Genie responses for manual review.

Runs the 9 anchor question pairs from demo-guide/flow.md against both Genie spaces:
the BEFORE question against the BEFORE space (Silver-only catalog) and the AFTER
question against the AFTER space (enriched Gold catalog). Writes a side-by-side
Markdown log to the results volume so the before/after gap can be reviewed
pair-by-pair.

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID_BEFORE      — required; BEFORE space (Silver-only)
  GENIE_SPACE_ID_AFTER       — required; AFTER space (enriched Gold)
  RESULTS_VOLUME_DIR         — required; UC Volume path for the Markdown log
  GENIE_TEST_RETRIES         — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage:
    python -m cli submit test_before_after.py
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
        "title": "Merchant favorites",
        "before": "Which merchants are most commonly visited by the top 10% of accounts by total dollar amount spent across merchants?",
        "after": "Which merchants are most commonly visited by accounts in ring-candidate communities?",
    },
    {
        "title": "Ring candidate book share",
        "before": "For the top 10% of accounts by transfer volume, what is the total balance held and what share of the book do they represent?",
        "after": "For ring-candidate communities taken together, what is the total balance held by their members and what share of the book do they represent?",
    },
    {
        "title": "Ring share of the book by region",
        "before": "What share of accounts send more than half their transfer volume to five or fewer repeat counterparties, broken out by region?",
        "after": "What share of accounts sits in communities flagged as ring candidates, broken out by region?",
    },
    {
        "title": "Investigator review queue",
        "before": "How many accounts are in the top 10% by transfer volume, and what is the regional breakdown of that workload?",
        "after": "How many accounts would need investigator review if the bar is high risk tier, and what is the regional breakdown of that workload?",
    },
    {
        "title": "Per-community internal vs external transfer ratio",
        "before": "For each account, what is the ratio of transfer volume sent to its top three counterparties versus everyone else, and how does that ratio distribute across the book?",
        "after": "For each ring-candidate community, what is the ratio of internal transfer volume between members to external transfer volume outside the community, and how does that ratio distribute across the candidate set?",
    },
    {
        "title": "Transfer count cohort",
        "before": "What is the average transfer count per account among accounts whose top three counterparties account for more than half their transfer volume, versus the general account population?",
        "after": "What is the average transfer count per account within ring-candidate communities versus the general account population?",
    },
    {
        "title": "Merchant spend mix by cohort",
        "before": "How does merchant-category spending mix differ between the top 10% of accounts by transfer volume and the baseline?",
        "after": "How does merchant-category spending mix differ between ring-community accounts and the baseline?",
    },
    {
        "title": "Merchant community concentration",
        "before": "Which merchants have a customer base concentrated in fewer than 20 accounts that together make up more than half of their transaction volume?",
        "after": "Are there merchants whose customer base is disproportionately concentrated in a single community?",
    },
    {
        "title": "Same-community transfer volume share",
        "before": "What fraction of total transfer volume flows between accounts that have transacted together 5 or more times, versus accounts with no prior transaction history?",
        "after": "What fraction of transfer volume flows between accounts in the same community versus across communities?",
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
        f"# Anchor pair BEFORE/AFTER review — {run_meta['timestamp_utc']}",
        "",
        f"- BEFORE space: `{run_meta['space_id_before']}`",
        f"- AFTER space: `{run_meta['space_id_after']}`",
        f"- Pairs: {len(pairs_with_results)}",
        "",
        "Each section pairs the BEFORE question (asked against the Silver-only space) "
        "with the AFTER question (asked against the enriched Gold space). "
        "Review: does the BEFORE answer sound plausible but miss the structural signal, "
        "and does the AFTER answer produce a specific, actionable result?",
        "",
    ]
    for idx, item in enumerate(pairs_with_results, start=1):
        pair = item["pair"]
        lines.extend([f"## {idx}. {pair['title']}", ""])
        lines.extend(_render_side("BEFORE", pair["before"], item["before_result"]))
        lines.extend(_render_side("AFTER", pair["after"], item["after_result"]))
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
    remote_path = f"{RESULTS_VOLUME_DIR}/anchor_pairs_review_{ts_safe}.md"
    w.files.upload(
        file_path=remote_path,
        contents=io.BytesIO(markdown.encode("utf-8")),
        overwrite=True,
    )
    print(f"\nLog written: {remote_path}")
    return 0


if __name__ == "__main__":
    main()
