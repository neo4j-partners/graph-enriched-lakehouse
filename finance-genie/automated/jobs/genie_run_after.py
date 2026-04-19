"""Submit wrapper: run genie_run.py against the AFTER (gold-table-enriched) Genie Space.

Usage:
    uv run python -m cli submit genie_run_after.py

Pass GATE=true to enable the legacy pass/fail threshold gating:
    Add GATE=true to .env before submitting, or use the GATE env-var mechanism.
"""

from __future__ import annotations

import os
import sys

from _cluster_bootstrap import inject_params

# Resolve GENIE_SPACE_ID and LABEL before genie_run imports os.environ["GENIE_SPACE_ID"].
# GENIE_SPACE_ID_AFTER is forwarded from .env by the CLI runner as a KEY=VALUE param.
inject_params()

os.environ["GENIE_SPACE_ID"] = os.environ["GENIE_SPACE_ID_AFTER"]
os.environ.setdefault("LABEL", "after")

import genie_run  # noqa: E402

exit_code = genie_run.main()
if exit_code:
    sys.exit(exit_code)
