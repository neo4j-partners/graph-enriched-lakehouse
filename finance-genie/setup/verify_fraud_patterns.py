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
import datetime
import json
import random
import sys
from pathlib import Path

import pandas as pd

SNAPSHOT_SCHEMA_VERSION = 1

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


# ── Snapshot IO ──────────────────────────────────────────────────────

def build_snapshot(checks: list, kind: str = "structural_checks") -> dict:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": SEED,
        "kind": kind,
        "checks": checks,
    }


def write_snapshot(snapshot: dict, path: Path) -> None:
    with open(path, "w") as fh:
        json.dump(snapshot, fh, indent=2, default=str)
    print(f"Snapshot written to {path.resolve()}", file=sys.stderr)


# ── Snapshot comparison ───────────────────────────────────────────────

def _compare_field(key, baseline_val, current_val, tolerance_pct):
    """Compare a single measured field. Returns a result dict."""
    if isinstance(baseline_val, list):
        if not isinstance(current_val, list) or len(current_val) != len(baseline_val):
            return {"key": key, "baseline": baseline_val, "current": current_val,
                    "diff_pct": None, "passed": False}
        sub = [_compare_field(f"{key}[{i}]", b, c, tolerance_pct)
               for i, (b, c) in enumerate(zip(baseline_val, current_val))]
        passed = all(s["passed"] for s in sub)
        return {"key": key, "baseline": baseline_val, "current": current_val,
                "diff_pct": None, "passed": passed, "elements": sub}
    if isinstance(baseline_val, float) and isinstance(current_val, (int, float)):
        if baseline_val == 0:
            passed = current_val == 0
            diff_pct = None if passed else float("inf")
        else:
            diff_pct = abs(current_val - baseline_val) / abs(baseline_val) * 100
            passed = diff_pct <= tolerance_pct
        return {"key": key, "baseline": baseline_val, "current": current_val,
                "diff_pct": round(diff_pct, 2) if diff_pct is not None and diff_pct != float("inf") else diff_pct,
                "passed": passed}
    # int or str: exact match
    passed = baseline_val == current_val
    return {"key": key, "baseline": baseline_val, "current": current_val,
            "diff_pct": None, "passed": passed}


def compare_snapshots(baseline: dict, current: dict, tolerance_pct: float = 5.0) -> dict:
    if baseline.get("schema_version") != current.get("schema_version"):
        raise SystemExit(
            f"Schema version mismatch: baseline={baseline.get('schema_version')}, "
            f"current={current.get('schema_version')}. Re-generate the baseline snapshot."
        )
    if baseline.get("kind") != current.get("kind"):
        raise SystemExit(
            f"Snapshot kind mismatch: baseline={baseline.get('kind')}, "
            f"current={current.get('kind')}."
        )

    current_by_name = {c["name"]: c for c in current.get("checks", [])}
    check_results = []

    for b_check in baseline.get("checks", []):
        name = b_check["name"]
        c_check = current_by_name.get(name)
        if c_check is None:
            check_results.append({
                "name": name, "passed": False,
                "error": "check not found in current run",
                "fields": [],
            })
            continue

        field_results = []
        for key, b_val in b_check.get("measured", {}).items():
            c_val = c_check.get("measured", {}).get(key)
            if c_val is None:
                field_results.append({"key": key, "baseline": b_val, "current": None,
                                      "diff_pct": None, "passed": False})
            else:
                field_results.append(_compare_field(key, b_val, c_val, tolerance_pct))

        current_passed = c_check.get("passed", False)
        fields_passed = all(f["passed"] for f in field_results)
        check_results.append({
            "name": name,
            "current_passed": current_passed,
            "fields_passed": fields_passed,
            "passed": current_passed and fields_passed,
            "fields": field_results,
        })

    overall = all(c["passed"] for c in check_results)
    return {"passed": overall, "tolerance_pct": tolerance_pct, "checks": check_results}


def render_comparison_report(comparison: dict) -> str:
    lines = ["# Snapshot Comparison Report", ""]
    overall = "PASS" if comparison["passed"] else "FAIL"
    lines.append(f"**Overall:** {overall}  |  tolerance: {comparison['tolerance_pct']}%")
    lines.append("")

    for c in comparison["checks"]:
        verdict = "PASS" if c["passed"] else "FAIL"
        lines.append(f"## {c['name']} — {verdict}")
        lines.append("")
        if c.get("error"):
            lines.append(f"**Error:** {c['error']}")
            lines.append("")
            continue
        if not c["current_passed"]:
            lines.append("**Note:** current check result is FAIL (independent of baseline drift)")
            lines.append("")
        lines.append("| Field | Baseline | Current | Diff% | Status |")
        lines.append("|-------|----------|---------|-------|--------|")
        for f in c["fields"]:
            if f.get("elements"):
                status = "PASS" if f["passed"] else "FAIL"
                lines.append(f"| {f['key']} | (list) | (list) | — | {status} |")
            else:
                diff = f["diff_pct"]
                diff_str = f"{diff:.2f}%" if isinstance(diff, float) else "—"
                status = "PASS" if f["passed"] else "FAIL"
                lines.append(f"| {f['key']} | {f['baseline']} | {f['current']} | {diff_str} | {status} |")
        lines.append("")

    return "\n".join(lines)


# ── Genie output checks ───────────────────────────────────────────────

def build_genie_expected() -> dict:
    """Hard-coded expected Genie results from GDS_FTW.md Test 1.

    The top_10_accounts list is the exact order Genie returned. Users can
    redirect this output to a file, edit the list to match a live Genie run,
    and then use it as --genie-json input.
    """
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "kind": "genie_output",
        "checks": [
            {
                "name": "Genie-Test1-Centrality",
                "description": "Which accounts are most central to the money flow?",
                "measured": {
                    "top_10_accounts": [18762, 11147, 3801, 15940, 7698, 22333, 708, 9088, 3563, 6041],
                    "whale_count": 10,
                    "fraud_count": 0,
                },
                "passed": True,
            }
        ],
    }


def check_genie_output(genie_snapshot: dict, whale_ids: set, fraud_ids: set) -> list:
    """Validate a recorded Genie output JSON against ground truth.

    Checks that the accounts Genie named are correctly labelled as whales
    (not fraud ring members), confirming the demo's before-GDS failure mode.
    """
    checks_out = []
    for entry in genie_snapshot.get("checks", []):
        top_accounts = entry.get("measured", {}).get("top_10_accounts", [])
        whale_count = int(sum(1 for a in top_accounts if a in whale_ids))
        fraud_count = int(sum(1 for a in top_accounts if a in fraud_ids))
        expected_whale = entry["measured"].get("whale_count")
        expected_fraud = entry["measured"].get("fraud_count")

        passed = (
            whale_count == expected_whale
            and fraud_count == expected_fraud
        )
        diagnostic = None
        if not passed:
            msgs = []
            if whale_count != expected_whale:
                msgs.append(f"whale_count {whale_count} != expected {expected_whale}")
            if fraud_count != expected_fraud:
                msgs.append(f"fraud_count {fraud_count} != expected {expected_fraud}")
            diagnostic = "; ".join(msgs)

        checks_out.append({
            "name": entry["name"],
            "target": (
                f"All top-10 accounts are whales (whale_count={expected_whale}), "
                f"no fraud ring members (fraud_count={expected_fraud})."
            ),
            "measured": {
                "top_10_accounts": top_accounts,
                "whale_count": whale_count,
                "fraud_count": fraud_count,
            },
            "diagnostic": diagnostic,
            "passed": passed,
        })
    return checks_out


# ── GDS output checks ─────────────────────────────────────────────────

def check_gds_output(gds_csv_path: Path, fraud_ids: set) -> list:
    """Validate enriched Account node properties exported from Databricks.

    Expects a CSV with columns:
        account_id, is_fraud, risk_score, community_id, similarity_score

    Returns three check dicts covering PageRank, Louvain, and Node Similarity
    distributions.
    """
    df = pd.read_csv(gds_csv_path)
    required = {"account_id", "is_fraud", "risk_score", "community_id", "similarity_score"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            f"GDS CSV is missing columns: {', '.join(sorted(missing))}. "
            "Export account_id, is_fraud, risk_score, community_id, similarity_score "
            "from Databricks notebook 03."
        )

    df["_is_fraud"] = df["account_id"].isin(fraud_ids)

    # ── PageRank ──────────────────────────────────────────────────────
    fraud_rs   = df[df["_is_fraud"]]["risk_score"]
    normal_rs  = df[~df["_is_fraud"]]["risk_score"]
    fraud_avg  = float(fraud_rs.mean()) if len(fraud_rs) else 0.0
    normal_avg = float(normal_rs.mean()) if len(normal_rs) else 0.0
    ratio_pr   = fraud_avg / normal_avg if normal_avg > 0 else float("inf")

    top20 = df.nlargest(20, "risk_score")
    top20_fraud_frac = float(top20["_is_fraud"].mean())

    pr_passed = ratio_pr >= 2.0 and top20_fraud_frac >= 0.5
    pr_diagnostic = None
    if not pr_passed:
        msgs = []
        if ratio_pr < 2.0:
            msgs.append(f"fraud_to_normal_ratio {ratio_pr:.2f} < 2.0")
        if top20_fraud_frac < 0.5:
            msgs.append(f"top_20_fraud_fraction {top20_fraud_frac:.2f} < 0.5")
        pr_diagnostic = "; ".join(msgs)

    pagerank_check = {
        "name": "GDS-PageRank-Distribution",
        "target": "fraud_to_normal_ratio >= 2.0, top_20_fraud_fraction >= 0.5",
        "measured": {
            "fraud_avg_risk_score":   round(fraud_avg, 6),
            "normal_avg_risk_score":  round(normal_avg, 6),
            "fraud_to_normal_ratio":  round(ratio_pr, 2) if ratio_pr != float("inf") else "inf",
            "top_20_fraud_fraction":  round(top20_fraud_frac, 3),
        },
        "diagnostic": pr_diagnostic,
        "passed": pr_passed,
    }

    # ── Louvain ───────────────────────────────────────────────────────
    community_sizes = df.groupby("community_id").size().rename("size")
    tight = community_sizes[community_sizes >= 80]
    tight_count = int(len(tight))

    top10_communities = community_sizes.nlargest(10).index.tolist()
    purities = []
    for cid in top10_communities:
        members = df[df["community_id"] == cid]
        purity = float(members["_is_fraud"].mean()) if len(members) else 0.0
        purities.append(purity)
    avg_purity = sum(purities) / len(purities) if purities else 0.0

    lv_passed = tight_count >= 8 and avg_purity >= 0.8
    lv_diagnostic = None
    if not lv_passed:
        msgs = []
        if tight_count < 8:
            msgs.append(f"tight_communities_count {tight_count} < 8 (expected ~10)")
        if avg_purity < 0.8:
            msgs.append(f"avg_fraud_purity_top10 {avg_purity:.2f} < 0.8")
        lv_diagnostic = "; ".join(msgs)

    louvain_check = {
        "name": "GDS-Louvain-Community-Purity",
        "target": "tight_communities_count >= 8, avg_fraud_purity_top10 >= 0.8",
        "measured": {
            "tight_communities_count": tight_count,
            "avg_fraud_purity_top10":  round(avg_purity, 3),
            "top10_community_purities": [round(p, 3) for p in purities],
        },
        "diagnostic": lv_diagnostic,
        "passed": lv_passed,
    }

    # ── Node Similarity ───────────────────────────────────────────────
    fraud_sim  = df[df["_is_fraud"]]["similarity_score"]
    normal_sim = df[~df["_is_fraud"]]["similarity_score"]
    fraud_sim_avg  = float(fraud_sim.mean()) if len(fraud_sim) else 0.0
    normal_sim_avg = float(normal_sim.mean()) if len(normal_sim) else 0.0
    ratio_sim = fraud_sim_avg / normal_sim_avg if normal_sim_avg > 0 else float("inf")

    ns_passed = ratio_sim >= 2.0
    ns_diagnostic = None
    if not ns_passed:
        ns_diagnostic = (
            f"within_ring_ratio {ratio_sim:.2f} < 2.0. "
            "Fraud accounts should have markedly higher max similarity_score than normal accounts."
        )

    nodesim_check = {
        "name": "GDS-NodeSimilarity-Distribution",
        "target": "within_ring_ratio (fraud_avg / normal_avg similarity_score) >= 2.0",
        "measured": {
            "fraud_avg_similarity":  round(fraud_sim_avg, 5),
            "normal_avg_similarity": round(normal_sim_avg, 5),
            "within_ring_ratio":     round(ratio_sim, 2) if ratio_sim != float("inf") else "inf",
        },
        "diagnostic": ns_diagnostic,
        "passed": ns_passed,
    }

    return [pagerank_check, louvain_check, nodesim_check]


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
    parser.add_argument(
        "--output-json", metavar="PATH",
        help="Write structural check results as a JSON snapshot to PATH.",
    )
    parser.add_argument(
        "--compare-json", metavar="PATH",
        help="Compare current structural results against a prior JSON snapshot at PATH.",
    )
    parser.add_argument(
        "--tolerance-pct", type=float, default=5.0,
        help="Relative tolerance in percent for float comparisons (default: 5.0).",
    )
    parser.add_argument(
        "--gds-csv", metavar="PATH",
        help="Path to enriched accounts CSV (account_id, is_fraud, risk_score, "
             "community_id, similarity_score). Runs GDS distribution checks.",
    )
    parser.add_argument(
        "--genie-json", metavar="PATH",
        help="Path to a recorded Genie output JSON snapshot. "
             "Validates whale/fraud account split.",
    )
    parser.add_argument(
        "--emit-genie-expected", action="store_true",
        help="Print the expected Genie output template as JSON and exit. "
             "Redirect to a file to use as a --genie-json baseline.",
    )
    args = parser.parse_args()

    if args.emit_genie_expected:
        print(json.dumps(build_genie_expected(), indent=2))
        sys.exit(0)

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

    structural_failed = not all(c["passed"] for c in checks)

    snapshot = build_snapshot(checks)

    if args.output_json:
        write_snapshot(snapshot, Path(args.output_json))

    if args.compare_json:
        baseline = json.loads(Path(args.compare_json).read_text())
        comparison = compare_snapshots(baseline, snapshot, args.tolerance_pct)
        print(render_comparison_report(comparison))
        if not comparison["passed"]:
            sys.exit(1)

    if args.gds_csv:
        gds_checks = check_gds_output(Path(args.gds_csv), fraud_ids)
        print(render_report(gds_checks))
        if args.output_json:
            gds_path = Path(args.output_json)
            gds_out = gds_path.with_stem(gds_path.stem + "_gds")
            write_snapshot(build_snapshot(gds_checks, kind="gds_output"), gds_out)
        if not all(c["passed"] for c in gds_checks):
            sys.exit(1)

    if args.genie_json:
        genie_data = json.loads(Path(args.genie_json).read_text())
        genie_checks = check_genie_output(genie_data, whale_ids, fraud_ids)
        print(render_report(genie_checks))
        if not all(c["passed"] for c in genie_checks):
            sys.exit(1)

    if structural_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
