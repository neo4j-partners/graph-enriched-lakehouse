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


# ── Seed ──────────────────────────────────────────────────────────────
SEED = _int("SEED", 42)

# ── Scale ─────────────────────────────────────────────────────────────
# These set dataset size. Change for larger/smaller datasets, not for
# signal tuning.
NUM_ACCOUNTS  = _int("NUM_ACCOUNTS",  25_000)
NUM_MERCHANTS = _int("NUM_MERCHANTS",  2_500)
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
# Current value (0.30) produces ~2726x density ratio.
# Lower this to weaken Louvain and PageRank signal.
WITHIN_RING_PROB = _float("WITHIN_RING_PROB", 0.30)

# Fraction of P2P links directed to whale accounts.
# Controls how strongly raw inbound count misdirects Genie.
# Reducing this makes whales less dominant in Genie's centrality query.
WHALE_INBOUND = _float("WHALE_INBOUND", 0.20)

# Fraction of P2P links originating from whale accounts.
# Gives whales bidirectional P2P volume so they resemble payment aggregators
# (high in, high out) rather than pure collection accounts. Outbound goes to
# random accounts — not ring members — to preserve the sender-peripherality
# property that PageRank uses to separate whales from ring members.
# Should be set equal to WHALE_INBOUND so inbound and outbound volumes match.
WHALE_OUTBOUND = _float("WHALE_OUTBOUND", 0.20)

# Probability a fraud account visits a ring-anchor merchant per transaction.
# Primary driver of within-ring Jaccard similarity.
# Current value (0.18) produces ~14.78x Jaccard ratio.
# Lower this to weaken Node Similarity signal.
RING_ANCHOR_PREF = _float("RING_ANCHOR_PREF", 0.18)

# Number of shared anchor merchants assigned per ring.
# Sets the Jaccard ceiling. Fewer anchors narrows the shared merchant pool.
RING_ANCHOR_CNT = _int("RING_ANCHOR_CNT", 5)

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
