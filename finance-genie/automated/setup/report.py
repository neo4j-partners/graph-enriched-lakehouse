"""Rich report rendering and JSON snapshot IO for verify_fraud_patterns.py."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

SNAPSHOT_SCHEMA_VERSION = 1

_console = Console()

_CHECK_DESCRIPTIONS = {
    "Whale-Hiding-PageRank": (
        "Verifies that synthetic 'whale' accounts dominate the top-200 inbound-degree "
        "positions, making them high-value targets for graph-based risk scoring."
    ),
    "Ten-Ring Density Ratio": (
        "Confirms that transfers inside fraud rings are far denser than the background "
        "graph, producing a clear structural signal for community-detection algorithms."
    ),
    "Anchor-Merchant Jaccard": (
        "Confirms that accounts in the same fraud ring share a distinctive set of "
        "merchant counterparties, yielding high within-ring Jaccard similarity."
    ),
    "Column-Signal Sanity": (
        "Verifies that tabular feature columns carry statistically measurable separation "
        "between fraud and non-fraud accounts."
    ),
    "Genie-CommunityPairs-Before-GDS": (
        "Verifies that Genie's best SQL approximation of community structure finds "
        "bilateral pairs (small clusters), not the 100-account rings that Louvain "
        "resolves. PASSES when Genie fails to surface a large ring footprint — "
        "confirming the gap that community detection closes."
    ),
    "Genie-MerchantOverlap-Before-GDS": (
        "Verifies that raw shared-merchant count (no Jaccard normalization) is dominated "
        "by high-volume normal accounts rather than ring pairs. PASSES when same-ring "
        "fraction is low — confirming the gap that Node Similarity closes."
    ),
}


def render_report_rich(checks) -> None:
    """Print a rich-formatted verification report to the terminal."""
    passed_count = sum(1 for c in checks if c["passed"])
    failed_count = len(checks) - passed_count
    overall_passed = failed_count == 0

    verdict_text = Text()
    if overall_passed:
        verdict_text.append("✅ PASS", style="bold green")
    else:
        verdict_text.append("❌ FAIL", style="bold red")
    verdict_text.append(
        f"  ({passed_count} passed, {failed_count} failed)",
        style="dim",
    )

    header = Text(justify="center")
    header.append("Fraud Pattern Verification Report\n", style="bold")
    header.append("Overall: ")
    header.append_text(verdict_text)

    _console.print()
    _console.print(Panel(header, box=box.ROUNDED, border_style="bold"))
    _console.print()

    for i, c in enumerate(checks, 1):
        check_passed = c["passed"]
        border_color = "green" if check_passed else "red"
        icon = "✅" if check_passed else "❌"
        verdict_label = "PASS" if check_passed else "FAIL"

        description = _CHECK_DESCRIPTIONS.get(c["name"], c.get("target", ""))

        body = Text()
        body.append(description, style="italic dim")
        body.append("\n\n")
        body.append("Target: ", style="bold")
        body.append(c.get("target", ""), style="dim")
        body.append("\n")

        metrics_table = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            padding=(0, 1),
        )
        metrics_table.add_column("Metric", style="cyan", no_wrap=True)
        metrics_table.add_column("Value")

        for k, v in c["measured"].items():
            metrics_table.add_row(str(k), str(v))

        panel_title = (
            f"[bold]Check {i} of {len(checks)}: {c['name']}[/bold]  "
            f"{icon} [{border_color}]{verdict_label}[/{border_color}]"
        )

        content_parts = [body, metrics_table]
        if c.get("diagnostic"):
            diag = Text()
            diag.append("\nDiagnostic: ", style="bold red")
            diag.append(c["diagnostic"], style="red")
            content_parts.append(diag)

        _console.print(
            Panel(
                Group(*content_parts),
                title=panel_title,
                border_style=border_color,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        _console.print()


def build_snapshot(checks: list, seed: int, kind: str = "structural_checks") -> dict:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "seed": seed,
        "kind": kind,
        "checks": checks,
    }


def write_snapshot(snapshot: dict, path: Path) -> None:
    with open(path, "w") as fh:
        json.dump(snapshot, fh, indent=2, default=str)
    print(f"Snapshot written to {path.resolve()}", file=sys.stderr)


def _compare_field(key, baseline_val, current_val, tolerance_pct):
    """Compare a single measured field. Returns a result dict."""
    if isinstance(baseline_val, list):
        if not isinstance(current_val, list) or len(current_val) != len(baseline_val):
            return {"key": key, "baseline": baseline_val, "current": current_val,
                    "diff_pct": None, "passed": False}
        sub = [_compare_field(f"{key}[{i}]", b, c, tolerance_pct)
               for i, (b, c) in enumerate(zip(baseline_val, current_val))]
        passed = all(s["passed"] for s in sub)
        return {"key": key, "baseline": baseline_val, "current": current_val,
                "diff_pct": None, "passed": passed, "elements": sub}
    if isinstance(baseline_val, float) and isinstance(current_val, (int, float)):
        if baseline_val == 0:
            passed = current_val == 0
            diff_pct = None if passed else float("inf")
        else:
            diff_pct = abs(current_val - baseline_val) / abs(baseline_val) * 100
            passed = diff_pct <= tolerance_pct
        return {
            "key": key, "baseline": baseline_val, "current": current_val,
            "diff_pct": round(diff_pct, 2) if diff_pct is not None and diff_pct != float("inf") else diff_pct,
            "passed": passed,
        }
    passed = baseline_val == current_val
    return {"key": key, "baseline": baseline_val, "current": current_val,
            "diff_pct": None, "passed": passed}


def compare_snapshots(baseline: dict, current: dict, tolerance_pct: float = 5.0) -> dict:
    if baseline.get("schema_version") != current.get("schema_version"):
        raise SystemExit(
            f"Schema version mismatch: baseline={baseline.get('schema_version')}, "
            f"current={current.get('schema_version')}. Re-generate the baseline snapshot."
        )
    if baseline.get("kind") != current.get("kind"):
        raise SystemExit(
            f"Snapshot kind mismatch: baseline={baseline.get('kind')}, "
            f"current={current.get('kind')}."
        )

    current_by_name = {c["name"]: c for c in current.get("checks", [])}
    check_results = []

    for b_check in baseline.get("checks", []):
        name = b_check["name"]
        c_check = current_by_name.get(name)
        if c_check is None:
            check_results.append({
                "name": name, "passed": False,
                "error": "check not found in current run",
                "fields": [],
            })
            continue

        field_results = []
        for key, b_val in b_check.get("measured", {}).items():
            c_val = c_check.get("measured", {}).get(key)
            if c_val is None:
                field_results.append({"key": key, "baseline": b_val, "current": None,
                                      "diff_pct": None, "passed": False})
            else:
                field_results.append(_compare_field(key, b_val, c_val, tolerance_pct))

        current_passed = c_check.get("passed", False)
        fields_passed = all(f["passed"] for f in field_results)
        check_results.append({
            "name": name,
            "current_passed": current_passed,
            "fields_passed": fields_passed,
            "passed": current_passed and fields_passed,
            "fields": field_results,
        })

    overall = all(c["passed"] for c in check_results)
    return {"passed": overall, "tolerance_pct": tolerance_pct, "checks": check_results}


def render_comparison_report_rich(comparison: dict) -> None:
    """Print a rich-formatted snapshot comparison report to the terminal."""
    overall_passed = comparison["passed"]
    tolerance = comparison["tolerance_pct"]

    verdict_text = Text()
    if overall_passed:
        verdict_text.append("✅ PASS", style="bold green")
    else:
        verdict_text.append("❌ FAIL", style="bold red")
    verdict_text.append(f"  |  tolerance: {tolerance}%", style="dim")

    header = Text(justify="center")
    header.append("Snapshot Comparison Report\n", style="bold")
    header.append("Overall: ")
    header.append_text(verdict_text)

    _console.print()
    _console.print(Panel(header, box=box.ROUNDED, border_style="bold"))
    _console.print()

    for c in comparison["checks"]:
        check_passed = c["passed"]
        border_color = "green" if check_passed else "red"
        icon = "✅" if check_passed else "❌"
        verdict_label = "PASS" if check_passed else "FAIL"
        panel_title = (
            f"[bold]{c['name']}[/bold]  "
            f"{icon} [{border_color}]{verdict_label}[/{border_color}]"
        )

        content_parts: list = []

        if c.get("error"):
            err = Text()
            err.append("Error: ", style="bold red")
            err.append(c["error"], style="red")
            content_parts.append(err)
        else:
            if not c.get("current_passed", True):
                note = Text()
                note.append(
                    "Note: current check result is FAIL (independent of baseline drift)\n",
                    style="bold yellow",
                )
                content_parts.append(note)

            fields_table = Table(
                show_header=True,
                header_style="bold cyan",
                box=box.SIMPLE,
                padding=(0, 1),
            )
            fields_table.add_column("Field", style="cyan", no_wrap=True)
            fields_table.add_column("Baseline")
            fields_table.add_column("Current")
            fields_table.add_column("Diff %")
            fields_table.add_column("Status")

            for f in c["fields"]:
                if f.get("elements"):
                    status_text = "✅ PASS" if f["passed"] else "❌ FAIL"
                    status_style = "green" if f["passed"] else "red"
                    fields_table.add_row(
                        f["key"], "(list)", "(list)", "—",
                        Text(status_text, style=status_style),
                    )
                else:
                    diff = f["diff_pct"]
                    diff_str = f"{diff:.2f}%" if isinstance(diff, float) else "—"
                    status_text = "✅ PASS" if f["passed"] else "❌ FAIL"
                    status_style = "green" if f["passed"] else "red"
                    fields_table.add_row(
                        str(f["key"]),
                        str(f["baseline"]),
                        str(f["current"]),
                        diff_str,
                        Text(status_text, style=status_style),
                    )

            content_parts.append(fields_table)

        _console.print(
            Panel(
                Group(*content_parts),
                title=panel_title,
                border_style=border_color,
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        _console.print()
