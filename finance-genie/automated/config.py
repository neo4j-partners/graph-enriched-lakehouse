"""Central configuration for the finance-genie generator and verifier.

Configuration is loaded from finance-genie/.env. Environment variables already
set in the shell take precedence over the file.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _automated_dir = Path(__file__).resolve().parent
    load_dotenv(_automated_dir.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; use shell environment or defaults


def _int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


# ── Seed ──────────────────────────────────────────────────────────────
SEED = _int("SEED", 42)

# ── Scale ─────────────────────────────────────────────────────────────
# These set dataset size. Change for larger/smaller datasets, not for
# signal tuning.
NUM_ACCOUNTS  = _int("NUM_ACCOUNTS",  25_000)
NUM_MERCHANTS = _int("NUM_MERCHANTS",  7_500)
NUM_TXN       = _int("NUM_TXN",      250_000)
NUM_P2P       = _int("NUM_P2P",      300_000)
FRAUD_RATE    = _float("FRAUD_RATE",    0.04)
N_RINGS       = _int("N_RINGS",            10)
WHALE_RATE    = _float("WHALE_RATE",   0.008)

# ── PRIMARY TUNING KNOBS ──────────────────────────────────────────────
# These parameters control graph signal strength. Adjust these to explore
# the GDS-only detection boundary.

# Fraction of P2P links that stay within a ring.
# Primary driver of the density ratio (within-ring vs background).
# Set to 0.35: internal edge ratio ~93%, density ratio ~3,400×, Louvain forms
# 10 clean communities (80% avg purity, 100% per-ring coverage). Below 0.25
# (~89% internal) per-ring variance causes some rings to merge into large
# background communities. See worklog/PARAMETER_CALIBRATION.md Tier 5.
WITHIN_RING_PROB = _float("WITHIN_RING_PROB", 0.35)

# Fraction of P2P links directed to whale accounts.
# Set to 0.14 so whale_inbound_avg ≈ 210 at NUM_P2P=300k.
# (0.14 × 300k / 200 whales = 210 per whale)
# Must stay above ring captain inbound (~155 at WITHIN_RING_PROB=0.35)
# so the whale-hiding property holds: naive inbound-sort finds whales, not
# ring captains. See PARAMETER_CALIBRATION.md Tier 5.
WHALE_INBOUND = _float("WHALE_INBOUND", 0.14)

# Probability a fraud account visits a ring-anchor merchant per transaction.
# Primary driver of within-ring Jaccard similarity.
# Set to 0.35: NodeSimilarity fraud/normal ratio ≈ 1.98× (threshold ≥ 1.9×).
# Below 0.25 the ratio drops to ~1.50× and the NodeSimilarity GDS check fails.
# See worklog/PARAMETER_CALIBRATION.md Tier 5.
RING_ANCHOR_PREF = _float("RING_ANCHOR_PREF", 0.35)
