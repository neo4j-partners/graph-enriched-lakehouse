"""Submit wrapper: run genie_run.py against the BEFORE (base-table-only) Genie Space.

Usage:
    uv run python -m cli submit genie_run_before.py
"""

from __future__ import annotations

import os
import sys

# Resolve GENIE_SPACE_ID and LABEL before genie_run imports os.environ["GENIE_SPACE_ID"].
# GENIE_SPACE_ID_BEFORE is forwarded from .env by the CLI runner as a KEY=VALUE param.
for _arg in sys.argv[1:]:
    if "=" in _arg and not _arg.startswith("-"):
        _key, _, _val = _arg.partition("=")
        os.environ.setdefault(_key, _val)

os.environ["GENIE_SPACE_ID"] = os.environ["GENIE_SPACE_ID_BEFORE"]
os.environ.setdefault("LABEL", "before")

import genie_run  # noqa: E402

exit_code = genie_run.main()
if exit_code:
    sys.exit(exit_code)
