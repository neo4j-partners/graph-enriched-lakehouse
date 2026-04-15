"""
Finance Genie — Fraud Pattern Verification Script

Measures the three structural fraud patterns in the generated dataset
(whale-PageRank, ten-ring density ratio, anchor-merchant Jaccard) plus
column-signal sanity checks, and reports each result against the targets
documented in finance-genie/README.md.

Prints a markdown report to stdout that can be copy-pasted into a pull
request description or an issue. Exits with status 1 if any check fails,
so the script is usable as a regression gate.

Usage:
    From the finance-genie/ directory (which contains pyproject.toml):
        uv run setup/verify_fraud_patterns.py
        uv run setup/verify_fraud_patterns.py --input ./data/
"""

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_data import (
    SEED,
    NUM_ACCOUNTS,
    NUM_P2P,
    N_RINGS,
    FRAUD_RATE,
    WHALE_RATE,
    WHALE_INBOUND,
    WITHIN_RING_PROB,
    RING_ANCHOR_CNT,
    RING_ANCHOR_PREF,
    build_ground_truth,
)


# ── IO ────────────────────────────────────────────────────────────────

def load_data(input_dir: Path) -> dict:
    return {
        "accounts":       pd.read_csv(input_dir / "accounts.csv"),
        "account_labels": pd.read_csv(input_dir / "account_labels.csv"),
        "merchants":      pd.read_csv(input_dir / "merchants.csv"),
        "transactions":   pd.read_csv(input_dir / "transactions.csv"),
        "account_links":  pd.read_csv(input_dir / "account_links.csv"),
    }


def verify_ground_truth_matches(labels_df: pd.DataFrame, fraud_ids: set) -> None:
    """Sanity-check that the seeded reconstruction matches the data on disk."""
    csv_fraud = set(labels_df[labels_df["is_fraud"]]["account_id"].astype(int))
    if csv_fraud != fraud_ids:
        raise SystemExit(
            "Reconstructed fraud_ids do not match account_labels.csv is_fraud column. "
            "The data was generated with a different SEED or different constants. "
            "Re-run setup/generate_data.py before verifying."
        )


# ── Pattern checks ────────────────────────────────────────────────────

def check_whale_pagerank(links_df, fraud_ids, whale_ids):
    inbound = (
        links_df.groupby("dst_account_id").size().rename("inbound").reset_index()
    )
    inbound = inbound.sort_values("inbound", ascending=False)

    top_200 = inbound.head(200)
    top_200_whale = int(top_200["dst_account_id"].isin(whale_ids).sum())
    top_200_fraud = int(top_200["dst_account_id"].isin(fraud_ids).sum())

    whale_inbound = inbound[inbound["dst_account_id"].isin(whale_ids)]["inbound"]
    fraud_inbound = inbound[inbound["dst_account_id"].isin(fraud_ids)]["inbound"]

    whale_avg = float(whale_inbound.mean()) if len(whale_inbound) else 0.0
    fraud_avg = float(fraud_inbound.mean()) if len(fraud_inbound) else 0.0

    inbound_lookup = inbound.set_index("dst_account_id")["inbound"].to_dict()
    whale_links = links_df[links_df["dst_account_id"].isin(whale_ids)]
    sender_inbound_counts = (
        pd.Series(whale_links["src_account_id"].unique())
        .map(lambda s: inbound_lookup.get(s, 0))
    )
    sender_avg = float(sender_inbound_counts.mean()) if len(sender_inbound_counts) else 0.0

    passed = (
        top_200_whale >= 180
        and top_200_fraud <= 20
        and 30 <= whale_avg <= 80
        and 5 <= fraud_avg <= 25
        and sender_avg < whale_avg / 2
    )

    diagnostic = None
    if not passed:
        drift = []
        if top_200_whale < 180:
            drift.append("top-200 inbound is not whale-dominated")
        if top_200_fraud > 20:
            drift.append("ring members appearing in top-200 inbound")
        if not (30 <= whale_avg <= 80):
            drift.append(f"whale_inbound_avg {whale_avg:.1f} outside [30, 80]")
        if not (5 <= fraud_avg <= 25):
            drift.append(f"fraud_ring_inbound_avg {fraud_avg:.1f} outside [5, 25]")
        if sender_avg >= whale_avg / 2:
            drift.append("whales are receiving from well-connected senders, not peripheral ones")
        diagnostic = (
            f"{'; '.join(drift)}. WHALE_INBOUND moves whale_inbound_avg; "
            "WITHIN_RING_PROB moves fraud_ring_inbound_avg."
        )

    return {
        "name": "Whale-Hiding-PageRank",
        "target": (
            "Top 200 by raw inbound dominated by whales (>=180), few ring members (<=20). "
            "whale_inbound_avg in [50, 60]. fraud_ring_inbound_avg ~12. "
            "Whale senders are peripheral (low avg inbound)."
        ),
        "measured": {
            "top_200_whales": top_200_whale,
            "top_200_fraud_members": top_200_fraud,
            "whale_inbound_avg": round(whale_avg, 1),
            "fraud_ring_inbound_avg": round(fraud_avg, 1),
            "whale_sender_avg_inbound": round(sender_avg, 2),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_ring_density(links_df, rings):
    acct_to_ring = {a: i for i, ring in enumerate(rings) for a in ring}

    src_ring = links_df["src_account_id"].map(acct_to_ring)
    dst_ring = links_df["dst_account_id"].map(acct_to_ring)

    in_same_ring   = src_ring.notna() & (src_ring == dst_ring)
    within_total   = int(in_same_ring.sum())
    other_total    = int(len(links_df) - within_total)

    per_ring_links   = []
    per_ring_density = []
    for i, ring in enumerate(rings):
        size     = len(ring)
        possible = size * (size - 1)  # directed pairs
        ring_n   = int(((src_ring == i) & (dst_ring == i)).sum())
        per_ring_links.append(ring_n)
        per_ring_density.append(ring_n / possible if possible > 0 else 0.0)

    within_ring_density = sum(per_ring_density) / len(per_ring_density)

    total_directed_pairs       = NUM_ACCOUNTS * (NUM_ACCOUNTS - 1)
    within_ring_directed_pairs = sum(len(r) * (len(r) - 1) for r in rings)
    other_directed_pairs       = total_directed_pairs - within_ring_directed_pairs
    background_density = (
        other_total / other_directed_pairs if other_directed_pairs > 0 else 0.0
    )

    ratio = (
        within_ring_density / background_density
        if background_density > 0 else float("inf")
    )

    passed = ratio >= 100

    diagnostic = None
    if not passed:
        diagnostic = (
            f"ratio {ratio:.1f} is below 100. WITHIN_RING_PROB moves within-ring "
            "density up; lowering N_RINGS concentrates links into fewer rings and "
            "raises per-ring density. README's stated 0.024 figure is unlikely to "
            "match constants — measured value is the ground truth."
        )

    return {
        "name": "Ten-Ring Density Ratio",
        "target": (
            "within_ring_density ~ 0.024, background_density ~ 0.00009, ratio ~ 268"
        ),
        "measured": {
            "within_ring_density": round(within_ring_density, 6),
            "background_density":  round(background_density, 8),
            "ratio":               round(ratio, 1) if ratio != float("inf") else "inf",
            "within_ring_links_total": within_total,
            "per_ring_link_counts":    per_ring_links,
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_anchor_jaccard(transactions_df, rings, fraud_ids, sample_cross_pairs=2000):
    acct_merchants = (
        transactions_df.groupby("account_id")["merchant_id"]
        .agg(set)
        .to_dict()
    )

    def jaccard(a, b):
        s1 = acct_merchants.get(a, set())
        s2 = acct_merchants.get(b, set())
        union_size = len(s1 | s2)
        return len(s1 & s2) / union_size if union_size > 0 else 0.0

    within_jaccards = []
    for ring in rings:
        ring_list = sorted(ring)
        n = len(ring_list)
        for i in range(n):
            for j in range(i + 1, n):
                within_jaccards.append(jaccard(ring_list[i], ring_list[j]))

    within_avg = sum(within_jaccards) / len(within_jaccards) if within_jaccards else 0.0

    normal_ids = sorted(set(range(1, NUM_ACCOUNTS + 1)) - fraud_ids)
    fraud_list = sorted(fraud_ids)

    cross_jaccards = []
    for _ in range(sample_cross_pairs):
        f = random.choice(fraud_list)
        n = random.choice(normal_ids)
        cross_jaccards.append(jaccard(f, n))

    cross_avg = sum(cross_jaccards) / len(cross_jaccards) if cross_jaccards else 0.0
    ratio = within_avg / cross_avg if cross_avg > 0 else float("inf")

    passed = ratio >= 1.4 and within_avg > 0.001

    diagnostic = None
    if not passed:
        diagnostic = (
            f"ratio {ratio:.2f} is below 1.4 or within_ring_jaccard {within_avg:.5f} "
            "is too small for Node Similarity to grade ring members above noise. "
            "RING_ANCHOR_PREF (visit rate) and RING_ANCHOR_CNT (anchor count per ring) "
            "both move within-ring Jaccard."
        )

    return {
        "name": "Anchor-Merchant Jaccard",
        "target": "within_ring_jaccard ~ 0.0044, cross_rate_jaccard ~ 0.0024, ratio ~ 1.78",
        "measured": {
            "within_ring_jaccard": round(within_avg, 5),
            "cross_rate_jaccard":  round(cross_avg, 5),
            "ratio":               round(ratio, 2) if ratio != float("inf") else "inf",
            "within_pairs_sampled": len(within_jaccards),
            "cross_pairs_sampled":  len(cross_jaccards),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_column_signals(accounts_df, transactions_df, merchants_df, fraud_ids):
    accounts_df = accounts_df.copy()
    accounts_df["_is_fraud"] = accounts_df["account_id"].isin(fraud_ids)

    txn_df = transactions_df.copy()
    txn_df["_is_fraud"] = txn_df["account_id"].isin(fraud_ids)

    high_risk_ids = set(merchants_df[merchants_df["risk_tier"] == "high"]["merchant_id"])
    txn_df["_is_high_risk"] = txn_df["merchant_id"].isin(high_risk_ids)

    def split(df, col):
        f = float(df[df["_is_fraud"]][col].mean())
        n = float(df[~df["_is_fraud"]][col].mean())
        return f, n

    bal_f,  bal_n  = split(accounts_df, "balance")
    age_f,  age_n  = split(accounts_df, "holder_age")
    amt_f,  amt_n  = split(txn_df, "amount")
    hour_f, hour_n = split(txn_df, "txn_hour")

    hr_f = float(txn_df[txn_df["_is_fraud"]]["_is_high_risk"].mean())
    hr_n = float(txn_df[~txn_df["_is_fraud"]]["_is_high_risk"].mean())

    def diff_pct(f, n):
        return abs(f - n) / n * 100 if n else 0.0

    columns = [
        ("balance",    bal_f,  bal_n),
        ("holder_age", age_f,  age_n),
        ("txn_amount", amt_f,  amt_n),
        ("txn_hour",   hour_f, hour_n),
    ]

    column_results = [
        {
            "column":      name,
            "fraud_mean":  round(f, 2),
            "normal_mean": round(n, 2),
            "diff_pct":    round(diff_pct(f, n), 2),
        }
        for name, f, n in columns
    ]

    # txn_amount is a deliberately preserved real-world weak signal (see README
    # step 3). The other columns stay at the strict <10% bar.
    column_thresholds = {
        "balance":    10,
        "holder_age": 10,
        "txn_amount": 15,
        "txn_hour":   10,
    }

    high_risk_gap_pp = abs(hr_f - hr_n) * 100
    columns_pass     = all(
        c["diff_pct"] < column_thresholds[c["column"]] for c in column_results
    )
    high_risk_pass   = high_risk_gap_pp < 5
    passed           = columns_pass and high_risk_pass

    diagnostic = None
    if not passed:
        leaked = [
            c["column"]
            for c in column_results
            if c["diff_pct"] >= column_thresholds[c["column"]]
        ]
        msgs   = []
        if leaked:
            msgs.append(f"leaked columns: {', '.join(leaked)}")
        if not high_risk_pass:
            msgs.append(f"high_risk_gap_pp {high_risk_gap_pp:.2f} >= 5")
        diagnostic = (
            f"{'; '.join(msgs)}. A column-level gap beyond its threshold means the "
            "generator is leaking more signal than the design budget allows. "
            "Rebalance the column's fraud-vs-normal distributions in "
            "generate_transactions() or generate_accounts()."
        )

    return {
        "name": "Column-Signal Sanity",
        "target": (
            "balance, holder_age, txn_hour: <10% relative difference between fraud "
            "and normal. txn_amount: <15% (deliberately preserved weak signal, see "
            "README step 3). High-risk merchant fraction gap <= 5 pp (README claim: "
            "23.4% vs 21.0%, gap 2.4)."
        ),
        "measured": {
            "columns": column_results,
            "high_risk_fraction_fraud_pct":  round(hr_f * 100, 2),
            "high_risk_fraction_normal_pct": round(hr_n * 100, 2),
            "high_risk_gap_pp":              round(high_risk_gap_pp, 2),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


# ── Report ────────────────────────────────────────────────────────────

def render_report(checks):
    lines   = ["# Fraud Pattern Verification Report", ""]
    overall = "PASS" if all(c["passed"] for c in checks) else "FAIL"
    lines.append(f"**Overall:** {overall}")
    lines.append("")

    for c in checks:
        verdict = "PASS" if c["passed"] else "FAIL"
        lines.append(f"## {c['name']} — {verdict}")
        lines.append("")
        lines.append(f"**Target:** {c['target']}")
        lines.append("")
        lines.append("**Measured:**")
        lines.append("")
        lines.append("```")
        for k, v in c["measured"].items():
            lines.append(f"{k}: {v}")
        lines.append("```")
        if c.get("diagnostic"):
            lines.append("")
            lines.append(f"**Gap diagnostic:** {c['diagnostic']}")
        lines.append("")

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Verify the structural fraud patterns in the generated dataset."
    )
    parser.add_argument(
        "--input",
        default="./data",
        help="Directory containing accounts.csv, account_labels.csv, merchants.csv, "
             "transactions.csv, account_links.csv (default: ./data)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir.resolve()}")

    print(f"Loading data from {input_dir.resolve()}", file=sys.stderr)
    data = load_data(input_dir)

    random.seed(SEED)
    rings, fraud_ids, whale_ids = build_ground_truth()
    verify_ground_truth_matches(data["account_labels"], fraud_ids)

    print(
        f"Reconstructed: {len(rings)} rings, {len(fraud_ids)} fraud accounts, "
        f"{len(whale_ids)} whales",
        file=sys.stderr,
    )

    checks = [
        check_whale_pagerank(data["account_links"], fraud_ids, whale_ids),
        check_ring_density(data["account_links"], rings),
        check_anchor_jaccard(data["transactions"], rings, fraud_ids),
        check_column_signals(
            data["accounts"], data["transactions"], data["merchants"], fraud_ids
        ),
    ]

    print(render_report(checks))

    if not all(c["passed"] for c in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
