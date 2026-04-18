"""Shared thresholds between pull_gold_tables.py and validate_gold_tables.py.

Changing any of these here changes the definition of a fraud-ring community —
both the build (pull_gold_tables.py) and the gate (validate_gold_tables.py) read
from this module so they cannot drift.
"""

from __future__ import annotations

RING_SIZE_LOW = 50
RING_SIZE_HIGH = 200
COMMUNITY_AVG_RISK_MIN = 1.0

# Thresholds for fraud_risk_tier='high' within a ring community.
# Values are referenced in gold_schema.sql's fraud_risk_tier COMMENT — update
# both files if these change.
HIGH_TIER_RISK_MIN = 0.5
HIGH_TIER_SIM_MIN = 0.12

TIER_HIGH = "high"
TIER_MEDIUM = "medium"
TIER_LOW = "low"
