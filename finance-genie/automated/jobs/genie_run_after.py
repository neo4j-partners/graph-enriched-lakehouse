"""Submit wrapper: run genie_run.py against the AFTER (gold-table-enriched) Genie Space.

After the Genie run completes, if `BEFORE_ARTIFACT` is set in `.env` (forwarded
to the job by the CLI runner as a KEY=VALUE parameter), reads both artifacts
from the UC Volume and prints a markdown comparison report to stdout. When the
path is not set, prints a one-line note explaining how to add the comparison.

Usage:
    # In .env (optional):
    #   BEFORE_ARTIFACT=/Volumes/.../genie_run_before_2026-04-18T17-00-00Z.json
    uv run python -m cli submit genie_run_after.py

Pass GATE=true to enable the legacy pass/fail threshold gating:
    Add GATE=true to .env before submitting, or use the GATE env-var mechanism.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from _cluster_bootstrap import inject_params

# Resolve GENIE_SPACE_ID and LABEL before genie_run imports os.environ["GENIE_SPACE_ID"].
# GENIE_SPACE_ID_AFTER is forwarded from .env by the CLI runner as a KEY=VALUE param.
inject_params()

os.environ["GENIE_SPACE_ID"] = os.environ["GENIE_SPACE_ID_AFTER"]
os.environ.setdefault("LABEL", "after")

# Parse --before-artifact from the remaining argv (inject_params strips KEY=VALUE args).
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--before-artifact", dest="before_artifact", default=None)
_args, _ = _parser.parse_known_args()
BEFORE_ARTIFACT = _args.before_artifact or os.environ.get("BEFORE_ARTIFACT")

import genie_run  # noqa: E402
from genie_run_artifact import ArtifactSchemaError, load_run_artifact  # noqa: E402


def _print_comparison(before_path: str, after: dict) -> None:
    """Load the BEFORE artifact from its UC Volume path and diff against the
    in-memory AFTER artifact produced by the just-completed run."""
    from compare_report import build_report

    try:
        before = load_run_artifact(before_path)
    except (FileNotFoundError, ArtifactSchemaError) as exc:
        print(f"\nCompare skipped — cannot read BEFORE artifact at {before_path}: {exc}")
        return

    compare_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print()
    print("=" * 62)
    print(f"BEFORE vs AFTER comparison — {compare_ts}")
    print("=" * 62)
    print(build_report(before, after, compare_ts))


exit_code, _after_path, after_artifact = genie_run.run()

if BEFORE_ARTIFACT:
    _print_comparison(BEFORE_ARTIFACT, after_artifact)
else:
    print(
        "\nTo include a BEFORE vs AFTER comparison, set "
        "BEFORE_ARTIFACT=<path-to-before-artifact.json> in .env and resubmit."
    )

if exit_code:
    sys.exit(exit_code)
