"""
Finance Genie — Synthetic Fraud Dataset Generator (v2)

25,000 accounts across 10 structured fraud rings designed to expose
the three gaps described in genie-demo.md:

  accounts.csv        25,000 rows  Bank accounts with KYC attributes
  merchants.csv        2,500 rows  Merchants with category and risk tier
  transactions.csv   250,000 rows  Account -> Merchant transactions
  account_links.csv   40,000 rows  Peer-to-peer account transfers

Fraud design principles:
  TABULAR signals are deliberately weak so Genie cannot separate fraud
  from normal on any single column.

  GRAPH signals are strong and correspond 1:1 to the three GDS algorithms:

  PageRank  — 200 normal "whale" accounts dominate raw P2P inbound count.
               Genie's sort-by-volume answer names whales, not the ring.
               PageRank elevates ring members because they receive from
               other high-PR ring nodes, not from peripheral accounts.

  Louvain   — 10 rings of ~100 accounts each.  Within-ring P2P links
               create dense communities.  Individual bilateral pair counts
               stay low (1-3), so Genie's pair-grouping misses the ring.
               Louvain assigns every ring member a shared community_id.

  NodeSim   — Each ring has 5 shared "anchor" high-risk merchants.  Ring
               members share those specific merchants → high intra-ring
               Jaccard.  Overall high-risk fraction is nearly the same for
               fraud and normal, so a column filter cannot find them.

Usage:
    From the finance-genie/ directory (which contains pyproject.toml):
        uv run setup/generate_data.py
        uv run setup/generate_data.py --output ./data/
"""

import argparse
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Scale ────────────────────────────────────────────────────────────
SEED          = 42
NUM_ACCOUNTS  = 25_000
NUM_MERCHANTS =  2_500
NUM_TXN       = 250_000
NUM_P2P       =  40_000
FRAUD_RATE    = 0.04       # 1,000 fraud accounts total

# ── Fraud ring structure ─────────────────────────────────────────────
N_RINGS          = 10      # 10 rings × ~100 accounts = 1,000 fraud accounts

# ── P2P link buckets ─────────────────────────────────────────────────
# 30 % within-ring  → ring community structure (Louvain signal)
# 20 % to whales    → whale accounts top raw inbound count (hides ring from Genie)
# 50 % fully random → background noise
WITHIN_RING_PROB = 0.30
WHALE_RATE       = 0.008   # 200 normal whale accounts
WHALE_INBOUND    = 0.20

# ── Merchant anchor preferences ───────────────────────────────────────
# Each ring is assigned RING_ANCHOR_CNT specific high-risk merchants.
# Fraud txns use a ring anchor 18 % of the time.  Overall high-risk
# fraction ends up nearly identical between fraud and normal accounts,
# so Genie's merchant-tier filter gives nothing useful.
RING_ANCHOR_CNT  = 5
RING_ANCHOR_PREF = 0.18


# ── Helpers ───────────────────────────────────────────────────────────

def _build_rings(num_accounts: int, fraud_rate: float, n_rings: int):
    """Partition fraud accounts into n_rings evenly-sized sets."""
    total_fraud = int(num_accounts * fraud_rate)
    ring_size   = total_fraud // n_rings
    remainder   = total_fraud % n_rings

    all_ids = list(range(1, num_accounts + 1))
    random.shuffle(all_ids)

    rings, start = [], 0
    for r in range(n_rings):
        size = ring_size + (1 if r < remainder else 0)
        rings.append(set(all_ids[start : start + size]))
        start += size

    return rings, set().union(*rings)


def build_ground_truth():
    """Reconstruct rings, fraud_ids, and whale_ids from the seeded RNG.

    Must be called immediately after random.seed(SEED) and before any other
    RNG-consuming step. Both generate_all() and the verification script call
    this so they see identical ring and whale identities.
    """
    rings, fraud_ids = _build_rings(NUM_ACCOUNTS, FRAUD_RATE, N_RINGS)
    normal_ids       = set(range(1, NUM_ACCOUNTS + 1)) - fraud_ids
    whale_ids        = set(random.sample(list(normal_ids), int(NUM_ACCOUNTS * WHALE_RATE)))
    return rings, fraud_ids, whale_ids


# ── Generators ────────────────────────────────────────────────────────

def generate_accounts() -> pd.DataFrame:
    account_types = ["checking", "savings", "business"]
    regions       = ["US-East", "US-West", "US-Central", "EU-West", "EU-East", "APAC"]
    base_date     = datetime(2018, 1, 1)

    rows = []
    for i in range(1, NUM_ACCOUNTS + 1):
        open_date = base_date + timedelta(days=random.randint(0, 1800))
        rows.append({
            "account_id":   i,
            "account_hash": hashlib.md5(f"acct-{i}".encode()).hexdigest()[:12],
            "account_type": random.choice(account_types),
            "region":       random.choice(regions),
            "balance":      round(random.uniform(100, 500_000), 2),
            "opened_date":  open_date.strftime("%Y-%m-%d"),
            "holder_age":   random.randint(18, 80),
        })
    return pd.DataFrame(rows)


def generate_account_labels(fraud_ids: set) -> pd.DataFrame:
    rows = [{"account_id": i, "is_fraud": i in fraud_ids} for i in range(1, NUM_ACCOUNTS + 1)]
    return pd.DataFrame(rows)


def generate_merchants() -> pd.DataFrame:
    categories = ["retail", "online", "restaurant", "travel",
                  "crypto", "gaming", "grocery", "utilities"]
    risk_tiers = ["low", "medium", "high"]
    regions    = ["US-East", "US-West", "US-Central", "EU-West", "EU-East", "APAC"]

    rows = []
    for i in range(1, NUM_MERCHANTS + 1):
        cat     = random.choice(categories)
        weights = [0.1, 0.3, 0.6] if cat in ("crypto", "gaming") else [0.6, 0.3, 0.1]
        tier    = random.choices(risk_tiers, weights=weights)[0]
        rows.append({
            "merchant_id":   i,
            "merchant_name": f"merchant_{i:04d}",
            "category":      cat,
            "risk_tier":     tier,
            "region":        random.choice(regions),
        })
    return pd.DataFrame(rows)


def generate_transactions(
    fraud_ids: set,
    rings: list,
    merchants_df: pd.DataFrame,
    ring_anchors: dict,          # ring_idx -> [merchant_id, ...]
) -> pd.DataFrame:
    all_ids   = merchants_df["merchant_id"].tolist()
    base_date = datetime(2024, 1, 1)

    acct_to_ring = {
        acct_id: ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct_id in ring
    }

    rows = []
    for txn_id in range(1, NUM_TXN + 1):
        acct_id  = random.randint(1, NUM_ACCOUNTS)
        is_fraud = acct_id in fraud_ids

        # Merchant selection:
        # Fraud accounts use their ring's anchor merchants 18 % of the time.
        # The anchors are picked from high-risk merchants, but the overall
        # high-risk fraction for fraud vs normal stays within ~3 pp — not
        # enough for Genie to separate on a merchant-tier filter.
        if is_fraud and random.random() < RING_ANCHOR_PREF:
            merch_id = random.choice(ring_anchors[acct_to_ring[acct_id]])
        else:
            merch_id = random.choice(all_ids)

        # Amount and hour: extremely subtle shift.
        # Lognormal distributions overlap heavily; tabular models
        # cannot cleanly separate fraud from normal on these columns alone.
        if is_fraud:
            amount = round(random.lognormvariate(4.1, 1.2), 2)
            hour   = random.choices(range(24), weights=[2]*6 + [3]*12 + [2]*6)[0]
        else:
            amount = round(random.lognormvariate(4.0, 1.2), 2)
            hour   = random.choices(range(24), weights=[1]*6 + [4]*12 + [2]*6)[0]

        ts = base_date + timedelta(
            days=random.randint(0, 89),
            hours=hour,
            minutes=random.randint(0, 59),
        )
        rows.append({
            "txn_id":        txn_id,
            "account_id":    acct_id,
            "merchant_id":   merch_id,
            "amount":        amount,
            "txn_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "txn_hour":      hour,
        })
    return pd.DataFrame(rows)


def generate_account_links(
    rings: list,
    whale_ids: set,
) -> pd.DataFrame:
    whale_list = list(whale_ids)
    base_date  = datetime(2024, 1, 1)

    rows = []
    for link_id in range(1, NUM_P2P + 1):
        r = random.random()

        if r < WITHIN_RING_PROB:
            # Within-ring: builds the community structure Louvain detects.
            # Pairs are sampled randomly within the ring so individual
            # bilateral counts stay low (1-3) — Genie's pair-grouping
            # can surface a few suspicious pairs but cannot reveal the
            # full ring of ~100 accounts.
            ring      = random.choice(rings)
            ring_list = list(ring)
            src, dst  = random.sample(ring_list, 2)

        elif r < WITHIN_RING_PROB + WHALE_INBOUND:
            # Transfer TO a whale: inflates whale raw inbound counts so
            # Genie's "sort by inbound volume" returns whales, not the
            # fraud ring.  PageRank demotes whales because they receive
            # from low-degree peripheral accounts.
            dst = random.choice(whale_list)
            src = random.randint(1, NUM_ACCOUNTS)
            while src == dst:
                src = random.randint(1, NUM_ACCOUNTS)

        else:
            # Fully random transfer — background noise.
            src = random.randint(1, NUM_ACCOUNTS)
            dst = random.randint(1, NUM_ACCOUNTS)
            while dst == src:
                dst = random.randint(1, NUM_ACCOUNTS)

        amount = round(random.lognormvariate(5.0, 1.5), 2)
        ts = base_date + timedelta(
            days=random.randint(0, 89),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        rows.append({
            "link_id":            link_id,
            "src_account_id":     src,
            "dst_account_id":     dst,
            "amount":             amount,
            "transfer_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return pd.DataFrame(rows)


# ── Orchestrator ──────────────────────────────────────────────────────

def generate_all(output_dir: Path) -> dict:
    """Generate all five tables and write them as CSV files to output_dir."""
    random.seed(SEED)
    output_dir.mkdir(parents=True, exist_ok=True)

    rings, fraud_ids, whale_ids = build_ground_truth()

    print("Generating accounts ...")
    accounts_df = generate_accounts()
    accounts_df.to_csv(output_dir / "accounts.csv", index=False)
    print(f"  accounts: {len(accounts_df):,}  |  fraud rings: {N_RINGS} × ~{len(fraud_ids)//N_RINGS}  "
          f"|  whale hubs: {len(whale_ids)}")

    print("Generating account labels ...")
    labels_df = generate_account_labels(fraud_ids)
    labels_df.to_csv(output_dir / "account_labels.csv", index=False)
    print(f"  account_labels: {len(labels_df):,}  |  fraud: {labels_df['is_fraud'].sum()}")

    print("Generating merchants ...")
    merchants_df = generate_merchants()
    merchants_df.to_csv(output_dir / "merchants.csv", index=False)

    # Assign anchor merchants to each ring after merchants are generated.
    # Anchors are sampled from ALL merchants (not just high-risk) so the
    # overall high-risk fraction stays the same for fraud and normal accounts.
    # The structural signal comes from shared SPECIFIC merchants, not merchant
    # tier — a column filter on risk_tier cannot find the fraud ring.
    all_merchant_ids = merchants_df["merchant_id"].tolist()
    high_risk_ids    = merchants_df[merchants_df["risk_tier"] == "high"]["merchant_id"].tolist()
    ring_anchors     = {
        ring_idx: random.sample(all_merchant_ids, RING_ANCHOR_CNT)
        for ring_idx in range(N_RINGS)
    }
    print(f"  merchants: {len(merchants_df):,}  |  high-risk: {len(high_risk_ids)}  "
          f"|  anchor merchants/ring: {RING_ANCHOR_CNT}")

    print("Generating transactions ...")
    txn_df = generate_transactions(fraud_ids, rings, merchants_df, ring_anchors)
    txn_df.to_csv(output_dir / "transactions.csv", index=False)
    print(f"  transactions: {len(txn_df):,}")

    print("Generating account links ...")
    links_df = generate_account_links(rings, whale_ids)
    links_df.to_csv(output_dir / "account_links.csv", index=False)
    print(f"  account_links: {len(links_df):,}")

    return {
        "accounts":        len(accounts_df),
        "account_labels":  len(labels_df),
        "merchants":       len(merchants_df),
        "transactions":    len(txn_df),
        "account_links":   len(links_df),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic fraud dataset as CSV files."
    )
    parser.add_argument(
        "--output",
        default="./data",
        help="Output directory for CSV files (default: ./data)",
    )
    args   = parser.parse_args()
    output = Path(args.output)
    print(f"Writing CSV files to: {output.resolve()}")
    counts = generate_all(output)
    print(f"\nDone. {sum(counts.values()):,} total rows written to {output.resolve()}/")
