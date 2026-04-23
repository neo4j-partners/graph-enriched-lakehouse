"""Hub-question snapshot runner — captures BEFORE/AFTER responses for the fraud-hub question.

Asks the single fraud-hub question that GENIE_SETUP.md documents as its before/after
snapshot:

    "Are there accounts acting as hubs of potentially fraudulent money movement networks?"

Against both the BEFORE space (Silver-only) and the AFTER space (enriched Gold).
Used to refresh the snapshot in workshop/GENIE_SETUP.md after the merchants.risk_tier
column was removed from the Silver catalog.

Environment variables (injected by the CLI runner as KEY=VALUE argv):
  GENIE_SPACE_ID_BEFORE      — required; BEFORE space (Silver-only)
  GENIE_SPACE_ID_AFTER       — required; AFTER space (enriched Gold)
  RESULTS_VOLUME_DIR         — required; UC Volume path for the Markdown log
  GENIE_TEST_RETRIES         — optional; attempts per question (default 2)
  GENIE_TEST_TIMEOUT_SECONDS — optional; per-attempt timeout (default 120)

Usage:
    python -m cli submit test_hub_question.py
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

PREVIEW_ROWS = 10


PAIRS = [
    {
        "title": "Anchor — Merchant favorites",
        "before": (
            "Which merchants are most commonly transacted with by the top 10% of accounts "
            "by total dollar amount spent across merchants?"
        ),
        "after": (
            "Which merchants show the highest concentration of ring-candidate transactions "
            "relative to the overall book? For the top 10, show each merchant's ring-candidate "
            "transaction share versus the ~5% baseline ring-candidate transaction share across the book."
        ),
    },
    {
        "title": "Anchor follow-up — Before vs after ranking comparison",
        "before": (
            "Which merchants are most commonly transacted with by the top 10% of accounts "
            "by total dollar amount spent across merchants?"
        ),
        "after": (
            "Rank the top 10 merchants by share of transactions from ring-candidate accounts. "
            "For each, also show where they rank among the top 10 merchants most visited by "
            "the top 10% of accounts by total spend, and flag whether they appear in both lists."
        ),
    },
    {
        "title": "Follow-on 1 — Internal transfer circulation",
        "before": (
            "For ring-candidate communities, what fraction of each community's total transfer "
            "volume flows between members inside the community versus to accounts outside? "
            "Show the top 5 communities by internal transfer ratio."
        ),
        "after": (
            "For ring-candidate communities, what fraction of each community's total transfer "
            "volume flows between members inside the community versus to accounts outside? "
            "Show the top 5 communities by internal transfer ratio."
        ),
    },
    {
        "title": "Follow-on 2 — Shared-merchant account pairs",
        "before": (
            "Which pairs of accounts have the highest similarity scores? Show the top 10 pairs "
            "with their similarity scores, whether they are in the same community, "
            "and their fraud risk tier."
        ),
        "after": (
            "Which pairs of accounts have the highest similarity scores? Show the top 10 pairs "
            "with their similarity scores, whether they are in the same community, "
            "and their fraud risk tier."
        ),
    },
    {
        "title": "Follow-on 3 — Investigator work queue",
        "before": (
            "Show the top 15 accounts by risk score within ring-candidate communities. "
            "Include their community ID, region, total transaction volume, and fraud risk tier."
        ),
        "after": (
            "Show the top 15 accounts by risk score within ring-candidate communities. "
            "Include their community ID, region, total transaction volume, and fraud risk tier."
        ),
    },
    {
        "title": "Follow-on 4 — Book exposure by risk tier",
        "before": (
            "What is the total account balance held by high-risk tier accounts, and what share "
            "of the total book does that represent? Break it down by region."
        ),
        "after": (
            "What is the total account balance held by high-risk tier accounts, and what share "
            "of the total book does that represent? Break it down by region."
        ),
    },
    {
        "title": "Validation A — Merchant ring-candidate share",
        "before": (
            "Which merchants are most commonly visited by the top 20 accounts "
            "by total transaction volume?"
        ),
        "after": (
            "For James-Conway, Cardenas and Sons, Johnson, Williams and May, and Meyer Ltd, "
            "what share of each merchant's customers are members of ring-candidate communities, "
            "and how does that compare to the book baseline?"
        ),
    },
    {
        "title": "Validation B — High-volume account community membership",
        "before": (
            "For the top 20 accounts by total transaction volume, how many unique "
            "merchants did each account visit?"
        ),
        "after": (
            "For accounts in the top 20 by total transaction volume, what is their "
            "community membership status and risk tier? Are those accounts concentrated "
            "in a small number of communities, or are they spread across the book?"
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
        f"# Hub-question snapshot — {run_meta['timestamp_utc']}",
        "",
        f"- BEFORE space: `{run_meta['space_id_before']}`",
        f"- AFTER space: `{run_meta['space_id_after']}`",
        f"- Pairs: {len(pairs_with_results)}",
        "",
        "Captures what Genie returns for the fraud-hub question on the current Silver "
        "and Gold catalogs. Used to refresh the before/after snapshot in "
        "workshop/GENIE_SETUP.md after the merchants.risk_tier column was removed.",
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
    remote_path = f"{RESULTS_VOLUME_DIR}/hub_question_snapshot_{ts_safe}.md"
    w.files.upload(
        file_path=remote_path,
        contents=io.BytesIO(markdown.encode("utf-8")),
        overwrite=True,
    )
    print(f"\nLog written: {remote_path}")
    return 0


if __name__ == "__main__":
    main()
