"""
config.py — Central configuration for the finance-genie generator and verifier.

All constants are read from a .env file located in the same directory as this
file. If no .env file is present, values fall back to the defaults listed here
so existing workflows are unaffected.

To override any value, copy automated/.env.sample to automated/.env and edit
the relevant lines. Environment variables already set in the shell take
precedence over the .env file.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed; use shell environment or defaults


def _int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


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
# These four parameters control graph signal strength. Adjust these
# across phases to find the GDS-only detection boundary.

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
# Must stay above ring captain inbound (~155 at WITHIN_RING_PROB=0.35,
# CAPTAIN_TRANSFER_PROB=0.02) so the whale-hiding property holds: naive
# inbound-sort finds whales, not ring captains. See PARAMETER_CALIBRATION.md Tier 5.
WHALE_INBOUND = _float("WHALE_INBOUND", 0.14)

# Fraction of P2P links originating from whale accounts.
# Gives whales bidirectional P2P volume so they resemble payment aggregators
# (high in, high out) rather than pure collection accounts. Outbound goes to
# random accounts — not ring members — to preserve the sender-peripherality
# property that PageRank uses to separate whales from ring members.
# Set equal to WHALE_INBOUND so inbound and outbound volumes match.
WHALE_OUTBOUND = _float("WHALE_OUTBOUND", 0.14)

# When True, each whale sends only to a pre-assigned fixed pool of recurring
# plain-normal-account recipients, matching the consistent-counterparty pattern
# of a real payment aggregator.  When False, outbound goes to random accounts.
WHALE_FIXED_OUTBOUND = _bool("WHALE_FIXED_OUTBOUND", True)

# Number of fixed recipients in each whale's outbound pool.
# Only used when WHALE_FIXED_OUTBOUND=True.  Recipients are sampled from plain
# normal accounts (not whales, not ring members) so they remain low-degree,
# preserving the sender-peripherality property that PageRank relies on.
WHALE_RECIPIENT_POOL_SIZE = _int("WHALE_RECIPIENT_POOL_SIZE", 30)

# Probability a fraud account visits a ring-anchor merchant per transaction.
# Primary driver of within-ring Jaccard similarity.
# Set to 0.35: NodeSimilarity fraud/normal ratio ≈ 1.98× (threshold ≥ 1.9×).
# Below 0.25 the ratio drops to ~1.50× and the NodeSimilarity GDS check fails.
# See worklog/PARAMETER_CALIBRATION.md Tier 5.
RING_ANCHOR_PREF = _float("RING_ANCHOR_PREF", 0.35)

# Number of shared anchor merchants assigned per ring.
# Sets the Jaccard ceiling. Fewer anchors narrows the shared merchant pool.
RING_ANCHOR_CNT = _int("RING_ANCHOR_CNT", 4)

# Number of captains designated per ring.
# Captains absorb CAPTAIN_TRANSFER_PROB of intra-ring inbound transfers,
# concentrating PageRank within the ring so captains surface in the top-20.
CAPTAIN_COUNT = _int("CAPTAIN_COUNT", 5)

# Fraction of within-ring transfers that route to a captain as receiver.
# Set to 0.02: at NUM_P2P=300k, captains receive ~12 extra inbound from routing,
# keeping captain total (~155) well below whale avg (~210) so the whale-hiding
# property holds. At 0.10 captains receive ~60 extra and breach the top-200.
# See worklog/PARAMETER_CALIBRATION.md Tier 3 for the failure analysis.
CAPTAIN_TRANSFER_PROB = _float("CAPTAIN_TRANSFER_PROB", 0.02)

# ── Transaction amount distributions ─────────────────────────────────
# Lognormal parameters for transaction amounts. The fraud/normal gap is
# already near-realistic (<3%). Change only to adjust tabular signal
# independently of the graph signal.
FRAUD_LOGNORM_MU     = _float("FRAUD_LOGNORM_MU",    4.1)
FRAUD_LOGNORM_SIGMA  = _float("FRAUD_LOGNORM_SIGMA",  1.2)
NORMAL_LOGNORM_MU    = _float("NORMAL_LOGNORM_MU",    4.0)
NORMAL_LOGNORM_SIGMA = _float("NORMAL_LOGNORM_SIGMA", 1.2)

# Lognormal parameters for P2P transfer amounts.
P2P_LOGNORM_MU    = _float("P2P_LOGNORM_MU",    5.0)
P2P_LOGNORM_SIGMA = _float("P2P_LOGNORM_SIGMA", 1.5)
