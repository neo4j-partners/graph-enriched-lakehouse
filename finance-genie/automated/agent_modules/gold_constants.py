"""Shared thresholds between pull_gold_tables.py and validate_gold_tables.py.

Changing any of these here changes the definition of a fraud-ring community —
both the build (pull_gold_tables.py) and the gate (validate_gold_tables.py) read
from this module so they cannot drift.
"""

from __future__ import annotations

RING_SIZE_LOW = 50
RING_SIZE_HIGH = 200
COMMUNITY_AVG_RISK_MIN = 1.0

TIER_HIGH = "high"
TIER_MEDIUM = "medium"
TIER_LOW = "low"
