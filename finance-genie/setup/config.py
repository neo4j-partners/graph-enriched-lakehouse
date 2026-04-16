"""
config.py — Central configuration for the finance-genie generator and verifier.

All constants are read from a .env file located in the finance-genie/ directory
(one level above this file). If no .env file is present, values fall back to the
defaults listed here so existing workflows are unaffected.

To override any value, copy finance-genie/.env.sample to finance-genie/.env and
edit the relevant lines. Environment variables already set in the shell take
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
NUM_P2P       = _int("NUM_P2P",       40_000)
FRAUD_RATE    = _float("FRAUD_RATE",    0.04)
N_RINGS       = _int("N_RINGS",            10)
WHALE_RATE    = _float("WHALE_RATE",   0.008)

# ── PRIMARY TUNING KNOBS ──────────────────────────────────────────────
# These four parameters control graph signal strength. Adjust these
# across phases to find the GDS-only detection boundary.

# Fraction of P2P links that stay within a ring.
# Primary driver of the density ratio (within-ring vs background).
# Raised to 0.50 (from 0.30) to strengthen ring PageRank signal.
# Lower this to weaken Louvain and PageRank signal.
WITHIN_RING_PROB = _float("WITHIN_RING_PROB", 0.50)

# Fraction of P2P links directed to whale accounts.
# Controls how strongly raw inbound count misdirects Genie.
# Reduced to 0.10 (from 0.20) to make whale edge dominance less extreme.
WHALE_INBOUND = _float("WHALE_INBOUND", 0.10)

# Fraction of P2P links originating from whale accounts.
# Gives whales bidirectional P2P volume so they resemble payment aggregators
# (high in, high out) rather than pure collection accounts. Outbound goes to
# random accounts — not ring members — to preserve the sender-peripherality
# property that PageRank uses to separate whales from ring members.
# Should be set equal to WHALE_INBOUND so inbound and outbound volumes match.
WHALE_OUTBOUND = _float("WHALE_OUTBOUND", 0.10)

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
# Raised to 0.40 (from 0.18) to boost ring signal above the noise floor.
# At 0.40, ring members visit ~2.8 of 5 anchors on average; combined with
# NUM_MERCHANTS=7500 (noise floor ~0.10-0.12), expected ratio ~1.5-2.0x.
# Lower this to weaken Node Similarity signal.
RING_ANCHOR_PREF = _float("RING_ANCHOR_PREF", 0.40)

# Number of shared anchor merchants assigned per ring.
# Sets the Jaccard ceiling. Fewer anchors narrows the shared merchant pool.
RING_ANCHOR_CNT = _int("RING_ANCHOR_CNT", 5)

# Number of captains designated per ring.
# Captains absorb CAPTAIN_TRANSFER_PROB of intra-ring inbound transfers,
# concentrating PageRank within the ring so captains surface in the top-20.
CAPTAIN_COUNT = _int("CAPTAIN_COUNT", 5)

# Fraction of within-ring transfers that route to a captain as receiver.
# At 0.50, half of intra-ring transfers target captains, concentrating
# inbound PageRank on 5 high-degree nodes per ring.
CAPTAIN_TRANSFER_PROB = _float("CAPTAIN_TRANSFER_PROB", 0.10)

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
