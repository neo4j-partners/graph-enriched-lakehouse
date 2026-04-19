"""Genie CSV checks and GDS output checks for verify_fraud_patterns.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def classify_pair(a: int, b: int, ring_by_account: dict) -> str:
    """Return 'same_ring', 'cross_ring', or 'unknown' for an account pair."""
    ra = ring_by_account.get(a)
    rb = ring_by_account.get(b)
    if ra is None or rb is None:
        return "unknown"
    return "same_ring" if ra == rb else "cross_ring"


def detect_genie_csv_type(df: pd.DataFrame) -> str:
    """Infer which Genie check a CSV represents from its column names.

    Column signatures:
        account_id_a + account_id_b + similarity_score      → similarity (after-GDS)
        account_id_a + account_id_b + shared_merchant_count → merchant_overlap (before-GDS)
        account_id_a + account_id_b (only)                  → community_pairs (before-GDS)
        account_id  + community_id                          → louvain (after-GDS)
        account_id  + risk_score                            → pagerank (after-GDS)
        account_id  (only)                                  → centrality (before-GDS)
    """
    cols = set(df.columns)
    if {"account_id_a", "account_id_b"}.issubset(cols):
        if "similarity_score" in cols:
            return "similarity"
        if "shared_merchant_count" in cols:
            return "merchant_overlap"
        return "community_pairs"
    if {"account_id", "community_id"}.issubset(cols):
        return "louvain"
    if {"account_id", "risk_score"}.issubset(cols):
        return "pagerank"
    if "account_id" in cols:
        return "centrality"
    raise SystemExit(
        f"Cannot determine check type from columns {sorted(cols)}. "
        "Expected one of: account_id (centrality), account_id+risk_score "
        "(pagerank), account_id+community_id (louvain), "
        "account_id_a+account_id_b+similarity_score (similarity), "
        "account_id_a+account_id_b+shared_merchant_count (merchant_overlap), or "
        "account_id_a+account_id_b (community_pairs)."
    )


def check_genie_centrality_csv(
    df: pd.DataFrame, whale_ids: set, fraud_ids: set
) -> dict:
    """Verify the before-GDS centrality result returns whales, not ring members.

    Genie sorts by raw inbound transfer count. The 200 whale accounts dominate
    that ranking. A passing result confirms the demo gap: Genie names whales
    instead of the fraud ring.
    """
    ids = df["account_id"].tolist()
    whale_count = int(sum(1 for a in ids if a in whale_ids))
    fraud_count = int(sum(1 for a in ids if a in fraud_ids))
    other_count = len(ids) - whale_count - fraud_count
    whale_fraction = whale_count / len(ids) if ids else 0.0

    passed = whale_fraction >= 0.7 and fraud_count == 0

    diagnostic = None
    if not passed:
        msgs = []
        if whale_fraction < 0.7:
            msgs.append(
                f"{whale_count}/{len(ids)} returned accounts are whales "
                "(expected >= 70%)"
            )
        if fraud_count > 0:
            msgs.append(
                f"{fraud_count} fraud ring members in result "
                "(expected 0 before GDS enrichment)"
            )
        diagnostic = "; ".join(msgs)

    return {
        "name": "Genie-Centrality-Before-GDS",
        "target": (
            "whale_fraction >= 0.70, fraud_ring_count == 0. "
            "Genie sorts by raw inbound count — whales dominate, ring members do not appear."
        ),
        "measured": {
            "returned_accounts": len(ids),
            "whale_count": whale_count,
            "fraud_ring_count": fraud_count,
            "other_count": other_count,
            "whale_fraction": round(whale_fraction, 3),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_genie_pagerank_csv(
    df: pd.DataFrame, fraud_ids: set, whale_ids: set
) -> dict:
    """Verify the post-PageRank result returns fraud ring members, not whales.

    After GDS writes risk_score back to the accounts table, Genie's same
    centrality question should surface ring members. A passing result confirms
    that PageRank closed the demo gap.
    """
    ids = df["account_id"].tolist()
    fraud_count = int(sum(1 for a in ids if a in fraud_ids))
    whale_count = int(sum(1 for a in ids if a in whale_ids))
    ring_fraction = fraud_count / len(ids) if ids else 0.0

    passed = ring_fraction >= 0.7 and whale_count == 0

    diagnostic = None
    if not passed:
        msgs = []
        if ring_fraction < 0.7:
            msgs.append(
                f"{fraud_count}/{len(ids)} returned accounts are ring members "
                "(expected >= 70%)"
            )
        if whale_count > 0:
            msgs.append(
                f"{whale_count} whale accounts still in result "
                "(PageRank should have demoted them)"
            )
        diagnostic = "; ".join(msgs)

    return {
        "name": "Genie-PageRank-After-GDS",
        "target": (
            "ring_member_fraction >= 0.70, whale_count == 0. "
            "Genie sorts by risk_score — ring members rise, whales drop out."
        ),
        "measured": {
            "returned_accounts": len(ids),
            "fraud_ring_count": fraud_count,
            "whale_count": whale_count,
            "ring_member_fraction": round(ring_fraction, 3),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_genie_louvain_csv(df: pd.DataFrame, rings: list) -> dict:
    """Verify that each Genie community maps cleanly to a single fraud ring.

    After Louvain assigns community_id to each account, Genie can group
    accounts by that column. Each community in the result should be composed
    almost entirely of accounts from one ring.
    """
    ring_by_account = {
        acct: ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct in ring
    }

    community_purities = {}
    for cid, group in df.groupby("community_id"):
        member_ids = group["account_id"].tolist()
        ring_counts = {}
        for a in member_ids:
            r = ring_by_account.get(a)
            if r is not None:
                ring_counts[r] = ring_counts.get(r, 0) + 1
        if ring_counts:
            dominant = max(ring_counts.values())
            purity = dominant / len(member_ids)
        else:
            purity = 0.0
        community_purities[int(cid)] = round(purity, 3)

    avg_purity = (
        sum(community_purities.values()) / len(community_purities)
        if community_purities else 0.0
    )
    community_count = len(community_purities)
    passed = avg_purity >= 0.5 and community_count > 0

    diagnostic = None
    if not passed:
        msgs = []
        if community_count == 0:
            msgs.append("no communities found in CSV")
        elif avg_purity < 0.5:
            msgs.append(
                f"avg_community_purity {avg_purity:.3f} < 0.50 "
                "(communities contain mixed ring members — Louvain may have merged rings "
                "or enrichment did not write back cleanly)"
            )
        diagnostic = "; ".join(msgs)

    return {
        "name": "Genie-Louvain-After-GDS",
        "target": (
            "avg_community_purity >= 0.50. "
            "Each community_id groups accounts predominantly from a single ring."
        ),
        "measured": {
            "communities_in_result": community_count,
            "avg_community_purity": round(avg_purity, 3),
            "per_community_purity": community_purities,
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_genie_similarity_csv(df: pd.DataFrame, rings: list) -> dict:
    """Verify that high-similarity account pairs belong to the same fraud ring.

    After Node Similarity scores merchant-set overlap, Genie returns account
    pairs with high similarity_score. Pairs from the same ring share anchor
    merchants; cross-ring pairs do not.
    """
    ring_by_account = {
        acct: ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct in ring
    }

    total_pairs = len(df)
    same_ring = 0
    cross_ring = 0
    unknown = 0

    for _, row in df.iterrows():
        label = classify_pair(int(row["account_id_a"]), int(row["account_id_b"]), ring_by_account)
        if label == "same_ring":
            same_ring += 1
        elif label == "cross_ring":
            cross_ring += 1
        else:
            unknown += 1

    same_ring_fraction = same_ring / total_pairs if total_pairs else 0.0
    passed = same_ring_fraction >= 0.7 and total_pairs > 0

    diagnostic = None
    if not passed:
        msgs = []
        if total_pairs == 0:
            msgs.append("no pairs found in CSV")
        elif same_ring_fraction < 0.7:
            msgs.append(
                f"{same_ring}/{total_pairs} pairs belong to the same ring "
                "(expected >= 70%); "
                f"{cross_ring} cross-ring, {unknown} involve normal accounts"
            )
        diagnostic = "; ".join(msgs)

    return {
        "name": "Genie-NodeSimilarity-After-GDS",
        "target": (
            "same_ring_fraction >= 0.70. "
            "High-similarity pairs should share a ring and its anchor merchants."
        ),
        "measured": {
            "total_pairs": total_pairs,
            "same_ring_pairs": same_ring,
            "cross_ring_pairs": cross_ring,
            "unknown_pairs": unknown,
            "same_ring_fraction": round(same_ring_fraction, 3),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_genie_community_pairs_csv(df: pd.DataFrame, rings: list) -> dict:
    """Verify that before-GDS community queries find pairs, not 100-account rings.

    This is a BEFORE-GDS check: it PASSES when Genie FAILS to surface a large
    ring footprint. Genie's best SQL approximation (bidirectional pair counts or
    transitive-closure CTE) finds ring members exchanging money, but cannot
    compute Louvain community boundaries. Even if the pairs are correct, the
    largest implied community visible in the result should be far smaller than
    the actual 100-account rings.

    Pass criterion: largest_ring_footprint <= 20 (Genie surfaced at most 20
    accounts from any single ring across all returned pairs).
    """
    ring_by_account = {
        acct: ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct in ring
    }

    total_pairs = len(df)
    same_ring = 0
    cross_ring = 0
    unknown = 0
    ring_account_sets: dict[int, set] = {}

    for _, row in df.iterrows():
        a = int(row["account_id_a"])
        b = int(row["account_id_b"])
        label = classify_pair(a, b, ring_by_account)
        if label == "same_ring":
            same_ring += 1
            ra = ring_by_account[a]
            ring_account_sets.setdefault(ra, set()).update([a, b])
        elif label == "cross_ring":
            cross_ring += 1
        else:
            unknown += 1

    largest_ring_footprint = (
        max(len(s) for s in ring_account_sets.values())
        if ring_account_sets else 0
    )

    passed = largest_ring_footprint <= 20 and total_pairs > 0

    diagnostic = None
    if not passed:
        if total_pairs == 0:
            diagnostic = "no pairs found in CSV"
        else:
            diagnostic = (
                f"largest_ring_footprint {largest_ring_footprint} > 20. "
                "Genie surfaced more ring accounts than expected for a pair-based query. "
                "This may indicate Genie wrote a recursive CTE that resolved a large "
                "fraction of a ring. The community-vs-pairs gap is narrower than intended."
            )

    return {
        "name": "Genie-CommunityPairs-Before-GDS",
        "target": (
            "largest_ring_footprint <= 20. "
            "Genie finds bilateral pairs or small clusters — not the 100-account rings "
            "that Louvain resolves. Check PASSES when Genie FAILS to surface the full ring."
        ),
        "measured": {
            "total_pairs": total_pairs,
            "same_ring_pairs": same_ring,
            "cross_ring_pairs": cross_ring,
            "unknown_pairs": unknown,
            "largest_ring_footprint": largest_ring_footprint,
            "rings_touched": len(ring_account_sets),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def check_genie_merchant_overlap_csv(df: pd.DataFrame, rings: list) -> dict:
    """Verify that raw shared-merchant count does not surface ring pairs.

    This is a BEFORE-GDS check: it PASSES when Genie FAILS to identify ring
    pairs via raw merchant overlap. Without Jaccard normalization, high-volume
    normal accounts sharing many merchants by volume dominate the top results.
    Ring pairs share 4–5 specific anchor merchants out of 2,500 total, which
    is a small absolute count compared to prolific normal account pairs.

    Pass criterion: same_ring_fraction < 0.30.
    """
    ring_by_account = {
        acct: ring_idx
        for ring_idx, ring in enumerate(rings)
        for acct in ring
    }

    total_pairs = len(df)
    same_ring = 0
    cross_ring = 0
    unknown = 0

    for _, row in df.iterrows():
        label = classify_pair(int(row["account_id_a"]), int(row["account_id_b"]), ring_by_account)
        if label == "same_ring":
            same_ring += 1
        elif label == "cross_ring":
            cross_ring += 1
        else:
            unknown += 1

    same_ring_fraction = same_ring / total_pairs if total_pairs else 0.0
    passed = same_ring_fraction < 0.30 and total_pairs > 0

    diagnostic = None
    if not passed:
        if total_pairs == 0:
            diagnostic = "no pairs found in CSV"
        else:
            diagnostic = (
                f"same_ring_fraction {same_ring_fraction:.3f} >= 0.30. "
                "Raw shared-merchant count is surfacing more ring pairs than expected. "
                "This may mean ring anchor merchants are too distinctive in absolute "
                "count terms, or high-volume normal accounts are underrepresented in "
                "the result. The Node Similarity gap is narrower than intended."
            )

    return {
        "name": "Genie-MerchantOverlap-Before-GDS",
        "target": (
            "same_ring_fraction < 0.30. "
            "Raw shared-merchant count is dominated by high-volume normal accounts, "
            "not ring pairs. Check PASSES when Genie FAILS to find the ring signal."
        ),
        "measured": {
            "total_pairs": total_pairs,
            "same_ring_pairs": same_ring,
            "cross_ring_pairs": cross_ring,
            "unknown_pairs": unknown,
            "same_ring_fraction": round(same_ring_fraction, 3),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def run_genie_csv_check(
    csv_path: Path,
    rings: list,
    fraud_ids: set,
    whale_ids: set,
) -> dict:
    """Load a Genie output CSV, detect its check type, and run the appropriate check."""
    df = pd.read_csv(csv_path, comment="#")
    check_type = detect_genie_csv_type(df)
    print(f"  {csv_path.name}: detected as '{check_type}' check", file=sys.stderr)

    if check_type == "centrality":
        return check_genie_centrality_csv(df, whale_ids, fraud_ids)
    if check_type == "community_pairs":
        return check_genie_community_pairs_csv(df, rings)
    if check_type == "merchant_overlap":
        return check_genie_merchant_overlap_csv(df, rings)
    if check_type == "pagerank":
        return check_genie_pagerank_csv(df, fraud_ids, whale_ids)
    if check_type == "louvain":
        return check_genie_louvain_csv(df, rings)
    return check_genie_similarity_csv(df, rings)


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


def _check_pagerank_dist(df: pd.DataFrame) -> dict:
    fraud_rs   = df[df["_is_fraud"]]["risk_score"]
    normal_rs  = df[~df["_is_fraud"]]["risk_score"]
    fraud_avg  = float(fraud_rs.mean()) if len(fraud_rs) else 0.0
    normal_avg = float(normal_rs.mean()) if len(normal_rs) else 0.0
    ratio_pr   = fraud_avg / normal_avg if normal_avg > 0 else float("inf")

    top20 = df.nlargest(20, "risk_score")
    top20_fraud_frac = float(top20["_is_fraud"].mean())

    passed = ratio_pr >= 2.0 and top20_fraud_frac >= 0.5
    diagnostic = None
    if not passed:
        msgs = []
        if ratio_pr < 2.0:
            msgs.append(f"fraud_to_normal_ratio {ratio_pr:.2f} < 2.0")
        if top20_fraud_frac < 0.5:
            msgs.append(f"top_20_fraud_fraction {top20_fraud_frac:.2f} < 0.5")
        diagnostic = "; ".join(msgs)

    return {
        "name": "GDS-PageRank-Distribution",
        "target": "fraud_to_normal_ratio >= 2.0, top_20_fraud_fraction >= 0.5",
        "measured": {
            "fraud_avg_risk_score":  round(fraud_avg, 6),
            "normal_avg_risk_score": round(normal_avg, 6),
            "fraud_to_normal_ratio": round(ratio_pr, 2) if ratio_pr != float("inf") else "inf",
            "top_20_fraud_fraction": round(top20_fraud_frac, 3),
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def _check_louvain_dist(df: pd.DataFrame) -> dict:
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

    passed = tight_count >= 8 and avg_purity >= 0.5
    diagnostic = None
    if not passed:
        msgs = []
        if tight_count < 8:
            msgs.append(f"tight_communities_count {tight_count} < 8 (expected ~10)")
        if avg_purity < 0.5:
            msgs.append(f"avg_fraud_purity_top10 {avg_purity:.2f} < 0.5")
        diagnostic = "; ".join(msgs)

    return {
        "name": "GDS-Louvain-Community-Purity",
        "target": "tight_communities_count >= 8, avg_fraud_purity_top10 >= 0.5",
        "measured": {
            "tight_communities_count":  tight_count,
            "avg_fraud_purity_top10":   round(avg_purity, 3),
            "top10_community_purities": [round(p, 3) for p in purities],
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


def _check_nodesim_dist(df: pd.DataFrame) -> dict:
    fraud_sim      = df[df["_is_fraud"]]["similarity_score"]
    normal_sim     = df[~df["_is_fraud"]]["similarity_score"]
    fraud_sim_avg  = float(fraud_sim.mean()) if len(fraud_sim) else 0.0
    normal_sim_avg = float(normal_sim.mean()) if len(normal_sim) else 0.0
    ratio_sim      = fraud_sim_avg / normal_sim_avg if normal_sim_avg > 0 else float("inf")

    passed = ratio_sim >= 2.0
    diagnostic = None
    if not passed:
        diagnostic = (
            f"within_ring_ratio {ratio_sim:.2f} < 2.0. "
            "Fraud accounts should have markedly higher max similarity_score than normal accounts."
        )

    return {
        "name": "GDS-NodeSimilarity-Distribution",
        "target": "within_ring_ratio (fraud_avg / normal_avg similarity_score) >= 2.0",
        "measured": {
            "fraud_avg_similarity":  round(fraud_sim_avg, 5),
            "normal_avg_similarity": round(normal_sim_avg, 5),
            "within_ring_ratio":     round(ratio_sim, 2) if ratio_sim != float("inf") else "inf",
        },
        "diagnostic": diagnostic,
        "passed": passed,
    }


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
    return [_check_pagerank_dist(df), _check_louvain_dist(df), _check_nodesim_dist(df)]
