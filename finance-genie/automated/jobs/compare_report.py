"""Pure markdown report builder for BEFORE/AFTER Genie run comparisons.

Shared by `genie_run_after.py` (cluster-side fold) and any local replay tool.
Depends only on `genie_run_artifact` and the standard library so it is safe to
upload to the cluster alongside other job scripts.
"""

from __future__ import annotations

from genie_run_artifact import (
    case_by_name,
    last_attempt,
    metric_key,
    metric_value,
)


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
