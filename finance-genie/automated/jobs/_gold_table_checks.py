"""Shared gold-table quality checks for the pipeline and demo backend."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from pyspark.sql import functions as F

from _gold_constants import (
    RING_SIZE_HIGH,
    RING_SIZE_LOW,
    TIER_HIGH,
)

RING_CANDIDATE_COUNT_EXPECTED = 10
RING_DOMINANCE_MIN = 0.80
HIGH_TIER_FRAC_MIN = 0.95
SAME_COMMUNITY_FRAC_MIN = 0.95
COUNTERPARTY_RATIO_MIN = 1.10
ANCHOR_CATEGORY_COUNT = 4
ALLOWED_TOPOLOGIES = ("star", "mesh", "chain")


@dataclass
class GoldCheckResult:
    name: str
    passed: bool
    detail: str
    problems: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def header(label: str) -> None:
    print(f"\n-- {label} " + "-" * max(0, 60 - len(label)))


def load_ground_truth(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_gold_table_checks(
    spark,
    catalog: str,
    schema: str,
    ground_truth_path: str,
    *,
    emit: bool = True,
) -> list[GoldCheckResult]:
    gold_accounts = f"`{catalog}`.`{schema}`.gold_accounts"
    gold_pairs = f"`{catalog}`.`{schema}`.gold_account_similarity_pairs"
    gold_rings = f"`{catalog}`.`{schema}`.gold_fraud_ring_communities"

    gt = load_ground_truth(ground_truth_path)
    rings = gt["rings"]
    ring_id_to_members: dict[int, set[int]] = {
        int(r["ring_id"]): {int(a) for a in r["account_ids"]} for r in rings
    }
    if emit:
        print(
            f"OK    ground_truth.json loaded: {len(rings)} rings, "
            f"{sum(len(m) for m in ring_id_to_members.values()):,} fraud accounts"
        )

    ring_rows = [
        (int(a), int(rid))
        for rid, members in ring_id_to_members.items()
        for a in members
    ]
    ring_df = spark.createDataFrame(ring_rows, ["account_id", "ring_id"]).cache()

    ga_df = (
        spark.table(gold_accounts)
        .select(
            "account_id",
            "community_id",
            "fraud_risk_tier",
            "txn_count_30d",
            "distinct_merchant_count_30d",
            "distinct_counterparty_count",
        )
        .cache()
    )
    gr_df = (
        spark.table(gold_rings)
        .select(
            "community_id",
            "is_ring_candidate",
            "member_count",
            "top_account_id",
            "total_volume_usd",
            "topology",
            "anchor_merchant_categories",
        )
        .cache()
    )
    rc_df = gr_df.filter(F.col("is_ring_candidate")).cache()

    try:
        results: list[GoldCheckResult] = []
        results.append(_check_ring_candidate_count(rc_df, emit))
        dominance_result, community_to_ring = _check_ring_dominance(
            rc_df, ga_df, ring_df, ring_id_to_members, emit
        )
        results.append(dominance_result)
        results.append(_check_ring_size_range(rc_df, emit))
        results.append(_check_high_tier_coverage(ga_df, ring_df, emit))
        results.append(
            _check_top_account_in_ring(
                rc_df, community_to_ring, ring_id_to_members, emit
            )
        )
        results.append(_check_same_community_pairs(spark, gold_pairs, ring_df, emit))
        results.append(_check_ring_volume(rc_df, emit))
        results.append(_check_ring_topology(rc_df, emit))
        results.append(_check_anchor_categories(gr_df, ga_df, ring_df, emit))
        results.append(_check_account_metric_ranges(ga_df, emit))
        results.append(_check_counterparty_separation(ga_df, ring_df, emit))
        return results
    finally:
        rc_df.unpersist()
        gr_df.unpersist()
        ga_df.unpersist()
        ring_df.unpersist()


def _result(
    name: str,
    detail: str,
    problems: list[str],
    metadata: dict[str, Any] | None = None,
) -> GoldCheckResult:
    return GoldCheckResult(
        name=name,
        passed=not problems,
        detail=detail,
        problems=problems,
        metadata=metadata or {},
    )


def _check_ring_candidate_count(rc_df, emit: bool) -> GoldCheckResult:
    name = "Ring candidate count"
    if emit:
        header("[1/11] Ring candidate count")
    rc_count = rc_df.count()
    if emit:
        print(f"      is_ring_candidate=true: {rc_count}")
    problems = []
    if rc_count != RING_CANDIDATE_COUNT_EXPECTED:
        problems.append(
            f"ring_candidate_count = {rc_count}, expected "
            f"{RING_CANDIDATE_COUNT_EXPECTED}"
        )
    detail = f"{rc_count} candidate communities"
    if emit and not problems:
        print("OK    exactly 10 ring candidates")
    return _result(
        name,
        detail,
        problems,
        {"measured": rc_count, "expected": RING_CANDIDATE_COUNT_EXPECTED},
    )


def _check_ring_dominance(
    rc_df,
    ga_df,
    ring_df,
    ring_id_to_members: dict[int, set[int]],
    emit: bool,
) -> tuple[GoldCheckResult, dict[int, int]]:
    name = "Dominant ring coverage"
    if emit:
        header("[2/11] Dominant ring coverage")
    rc_members = (
        rc_df.select("community_id", "member_count")
        .join(ga_df.select("account_id", "community_id"), "community_id")
    )
    per_community = (
        rc_members.join(ring_df, "account_id", "left")
        .groupBy("community_id", "member_count")
        .agg(F.collect_list("ring_id").alias("ring_ids"))
    ).collect()

    problems: list[str] = []
    community_to_ring: dict[int, int] = {}
    ring_to_community: dict[int, int] = {}
    records: list[dict[str, Any]] = []

    for row in per_community:
        cid = int(row["community_id"])
        member_count = int(row["member_count"])
        ring_ids = [int(x) for x in row["ring_ids"] if x is not None]
        if not ring_ids:
            problems.append(
                f"community {cid}: no ground-truth ring members in a "
                "ring-candidate community"
            )
            continue

        counts: dict[int, int] = {}
        for rid in ring_ids:
            counts[rid] = counts.get(rid, 0) + 1
        dominant_ring, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        ring_size = len(ring_id_to_members[dominant_ring])
        dominance = dominant_count / ring_size
        community_to_ring[cid] = dominant_ring
        if dominant_ring in ring_to_community:
            problems.append(
                f"ring split: communities {ring_to_community[dominant_ring]} "
                f"and {cid} are both dominated by ring {dominant_ring}"
            )
        else:
            ring_to_community[dominant_ring] = cid

        records.append(
            {
                "community_id": cid,
                "member_count": member_count,
                "dominant_ring": dominant_ring,
                "ring_members_in_community": dominant_count,
                "ring_dominance": round(dominance, 3),
            }
        )
        if emit:
            print(
                f"      community {cid} (size {member_count}): dominant ring="
                f"{dominant_ring} ({dominant_count}/{ring_size} = {dominance:.0%})"
            )
        if dominance < RING_DOMINANCE_MIN:
            problems.append(
                f"community {cid}: dominant ring dominance {dominance:.0%} < "
                f"{RING_DOMINANCE_MIN:.0%}"
            )

    detail = f"{len(community_to_ring)} candidate communities mapped to rings"
    return _result(name, detail, problems, {"records": records}), community_to_ring


def _check_ring_size_range(rc_df, emit: bool) -> GoldCheckResult:
    name = "Ring candidate size range"
    if emit:
        header("[3/11] Ring candidate size range")
    row = rc_df.agg(
        F.min("member_count").alias("min_size"),
        F.max("member_count").alias("max_size"),
        F.sum(
            F.when(
                ~F.col("member_count").between(RING_SIZE_LOW, RING_SIZE_HIGH),
                1,
            ).otherwise(0)
        ).alias("out_of_range"),
    ).collect()[0]
    out_of_range = int(row["out_of_range"] or 0)
    min_size = int(row["min_size"]) if row["min_size"] is not None else None
    max_size = int(row["max_size"]) if row["max_size"] is not None else None
    if emit:
        print(
            f"      member_count range: {min_size}-{max_size}  "
            f"out_of_range: {out_of_range}"
        )
    problems = []
    if out_of_range:
        problems.append(
            f"{out_of_range} ring-candidate communities have member_count "
            f"outside [{RING_SIZE_LOW}, {RING_SIZE_HIGH}]"
        )
    elif emit:
        print("OK    all ring candidates in range")
    return _result(
        name,
        f"range {min_size}-{max_size}",
        problems,
        {
            "low": RING_SIZE_LOW,
            "high": RING_SIZE_HIGH,
            "min": min_size,
            "max": max_size,
            "out_of_range": out_of_range,
        },
    )


def _check_high_tier_coverage(ga_df, ring_df, emit: bool) -> GoldCheckResult:
    name = "High risk tier coverage"
    if emit:
        header("[4/11] High risk tier coverage")
    fraud_df = ring_df.select("account_id").distinct()
    rows = (
        fraud_df.join(ga_df.select("account_id", "fraud_risk_tier"), "account_id", "left")
        .groupBy("fraud_risk_tier")
        .count()
        .collect()
    )
    tier_counts = {r["fraud_risk_tier"]: int(r["count"]) for r in rows}
    total_ring_members = sum(tier_counts.values())
    high_count = tier_counts.get(TIER_HIGH, 0)
    high_frac = high_count / total_ring_members if total_ring_members else 0.0
    if emit:
        print(f"      ring members by tier: {tier_counts}")
        print(
            f"      fraud_risk_tier='high' coverage: "
            f"{high_count}/{total_ring_members} = {high_frac:.1%}"
        )
    problems = []
    if high_frac < HIGH_TIER_FRAC_MIN:
        problems.append(
            f"fraud_risk_tier='high' coverage {high_frac:.1%} < "
            f"{HIGH_TIER_FRAC_MIN:.0%}"
        )
    elif emit:
        print(f"OK    coverage {high_frac:.1%} >= {HIGH_TIER_FRAC_MIN:.0%}")
    return _result(
        name,
        f"{high_frac:.1%} of ring members are high risk",
        problems,
        {
            "high_count": high_count,
            "total_ring_members": total_ring_members,
            "fraction": round(high_frac, 4),
            "threshold": HIGH_TIER_FRAC_MIN,
        },
    )


def _check_top_account_in_ring(
    rc_df,
    community_to_ring: dict[int, int],
    ring_id_to_members: dict[int, set[int]],
    emit: bool,
) -> GoldCheckResult:
    name = "Top account belongs to dominant ring"
    if emit:
        header("[5/11] Top account belongs to dominant ring")
    problems: list[str] = []
    records: list[dict[str, Any]] = []
    for row in rc_df.select("community_id", "top_account_id").collect():
        cid = int(row["community_id"])
        top_id = int(row["top_account_id"]) if row["top_account_id"] is not None else None
        if top_id is None:
            problems.append(f"community {cid}: top_account_id is null")
            continue
        dominant_ring = community_to_ring.get(cid)
        if dominant_ring is None:
            continue
        in_ring = top_id in ring_id_to_members[dominant_ring]
        records.append(
            {
                "community_id": cid,
                "top_account_id": top_id,
                "dominant_ring": dominant_ring,
                "in_ring": in_ring,
            }
        )
        if emit:
            status = "OK " if in_ring else "BAD"
            print(
                f"      {status}  community {cid}: top_account_id={top_id} "
                f"(ring {dominant_ring} membership: {in_ring})"
            )
        if not in_ring:
            problems.append(
                f"community {cid}: top_account_id {top_id} not in dominant "
                f"ring {dominant_ring}"
            )
    return _result(
        name,
        f"{sum(1 for r in records if r['in_ring'])}/{len(records)} top accounts match",
        problems,
        {"records": records},
    )


def _check_same_community_pairs(
    spark,
    gold_pairs_table: str,
    ring_df,
    emit: bool,
) -> GoldCheckResult:
    name = "Same ring similarity pairs"
    if emit:
        header("[6/11] Same ring similarity pairs")
    pairs_with_rings = (
        spark.table(gold_pairs_table)
        .select("account_id_a", "account_id_b", "same_community")
        .join(
            ring_df.withColumnRenamed("account_id", "account_id_a")
            .withColumnRenamed("ring_id", "ring_id_a"),
            "account_id_a",
        )
        .join(
            ring_df.withColumnRenamed("account_id", "account_id_b")
            .withColumnRenamed("ring_id", "ring_id_b"),
            "account_id_b",
        )
        .filter(F.col("ring_id_a") == F.col("ring_id_b"))
    )
    row = pairs_with_rings.agg(
        F.count("*").alias("total"),
        F.sum(F.col("same_community").cast("int")).alias("true_count"),
    ).collect()[0]
    total = int(row["total"] or 0)
    true_count = int(row["true_count"] or 0)
    frac = true_count / total if total else 0.0
    if emit:
        print(
            f"      same-ring pairs in gold_account_similarity_pairs: {total:,}  "
            f"same_community=true: {true_count:,} ({frac:.1%})"
        )
    problems = []
    if total == 0:
        problems.append(
            "no same-ring pairs present in gold_account_similarity_pairs"
        )
    elif frac < SAME_COMMUNITY_FRAC_MIN:
        problems.append(
            f"same-ring same_community fraction {frac:.1%} < "
            f"{SAME_COMMUNITY_FRAC_MIN:.0%}"
        )
    elif emit:
        print(f"OK    same-ring fraction {frac:.1%} >= {SAME_COMMUNITY_FRAC_MIN:.0%}")
    return _result(
        name,
        f"{frac:.1%} same-ring pairs share a community",
        problems,
        {
            "same_ring_total": total,
            "same_community_true": true_count,
            "fraction": round(frac, 4),
            "threshold": SAME_COMMUNITY_FRAC_MIN,
        },
    )


def _check_ring_volume(rc_df, emit: bool) -> GoldCheckResult:
    name = "Ring transfer volume populated"
    if emit:
        header("[7/11] Ring transfer volume populated")
    row = rc_df.agg(
        F.count("*").alias("total"),
        F.sum(
            F.when(F.col("total_volume_usd") > 0, 1).otherwise(0)
        ).alias("positive"),
    ).collect()[0]
    total = int(row["total"] or 0)
    positive = int(row["positive"] or 0)
    problems = []
    if positive != total:
        problems.append(
            f"{total - positive} ring-candidate communities have non-positive "
            "total_volume_usd"
        )
    if emit:
        print(f"      positive total_volume_usd: {positive}/{total}")
    return _result(
        name,
        f"{positive}/{total} candidate communities have positive volume",
        problems,
        {"positive": positive, "total": total},
    )


def _check_ring_topology(rc_df, emit: bool) -> GoldCheckResult:
    name = "Ring topology populated"
    if emit:
        header("[8/11] Ring topology populated")
    bad_rows = (
        rc_df
        .filter(
            F.col("topology").isNull()
            | ~F.col("topology").isin(*ALLOWED_TOPOLOGIES)
        )
        .select("community_id", "topology")
        .collect()
    )
    counts = {
        r["topology"]: int(r["count"])
        for r in rc_df.groupBy("topology").count().collect()
    }
    if emit:
        print(f"      topology counts: {counts}")
    problems = [
        f"community {int(r['community_id'])}: invalid topology {r['topology']!r}"
        for r in bad_rows
    ]
    return _result(
        name,
        f"{sum(counts.values()) - len(bad_rows)}/{sum(counts.values())} valid values",
        problems,
        {"counts": counts, "allowed": list(ALLOWED_TOPOLOGIES)},
    )


def _check_anchor_categories(rc_df, ga_df, ring_df, emit: bool) -> GoldCheckResult:
    name = "Anchor merchant categories populated"
    if emit:
        header("[9/11] Anchor merchant categories populated")
    mapped_communities = (
        ring_df
        .join(ga_df.select("account_id", "community_id"), "account_id", "left")
        .filter(F.col("community_id").isNotNull())
        .select("community_id")
        .distinct()
    )
    checked = (
        mapped_communities
        .join(
            rc_df.select("community_id", "anchor_merchant_categories"),
            "community_id",
            "left",
        )
        .withColumn("category_count", F.size("anchor_merchant_categories"))
    )
    bad_rows = (
        checked
        .filter(F.col("category_count") != ANCHOR_CATEGORY_COUNT)
        .select("community_id", "category_count")
        .collect()
    )
    total = checked.count()
    if emit:
        print(
            f"      mapped communities with {ANCHOR_CATEGORY_COUNT} categories: "
            f"{total - len(bad_rows)}/{total}"
        )
    problems = [
        f"community {int(r['community_id'])}: anchor category count "
        f"{r['category_count']}"
        for r in bad_rows
    ]
    return _result(
        name,
        f"{total - len(bad_rows)}/{total} mapped communities have 4 categories",
        problems,
        {"total": total, "bad": len(bad_rows)},
    )


def _check_account_metric_ranges(ga_df, emit: bool) -> GoldCheckResult:
    name = "Account behavior metrics are non-negative"
    if emit:
        header("[10/11] Account behavior metrics are non-negative")
    metric_cols = [
        "txn_count_30d",
        "distinct_merchant_count_30d",
        "distinct_counterparty_count",
    ]
    row = ga_df.agg(
        *[
            F.sum(
                F.when(F.col(col).isNull() | (F.col(col) < 0), 1).otherwise(0)
            ).alias(col)
            for col in metric_cols
        ]
    ).collect()[0]
    bad_counts = {col: int(row[col] or 0) for col in metric_cols}
    if emit:
        print(f"      invalid metric counts: {bad_counts}")
    problems = [
        f"{col} has {count} null or negative values"
        for col, count in bad_counts.items()
        if count
    ]
    return _result(
        name,
        "all account behavior metrics are non-negative" if not problems else "invalid values found",
        problems,
        {"bad_counts": bad_counts},
    )


def _check_counterparty_separation(ga_df, ring_df, emit: bool) -> GoldCheckResult:
    name = "Ring members have higher counterparty counts"
    if emit:
        header("[11/11] Ring members have higher counterparty counts")
    fraud_accounts = (
        ring_df
        .select("account_id")
        .distinct()
        .withColumn("is_ring_member", F.lit(True))
    )
    scored = (
        ga_df
        .select("account_id", "distinct_counterparty_count")
        .join(fraud_accounts, "account_id", "left")
        .withColumn(
            "is_ring_member",
            F.coalesce(F.col("is_ring_member"), F.lit(False)),
        )
    )
    row = scored.agg(
        F.avg(
            F.when(F.col("is_ring_member"), F.col("distinct_counterparty_count"))
        ).alias("ring_avg"),
        F.avg(
            F.when(~F.col("is_ring_member"), F.col("distinct_counterparty_count"))
        ).alias("non_ring_avg"),
    ).collect()[0]
    ring_avg = float(row["ring_avg"] or 0.0)
    non_ring_avg = float(row["non_ring_avg"] or 0.0)
    ratio = ring_avg / non_ring_avg if non_ring_avg else float("inf")
    if emit:
        print(
            f"      ring avg={ring_avg:.2f}  non-ring avg={non_ring_avg:.2f}  "
            f"ratio={ratio:.2f}x"
        )
    problems = []
    if ratio < COUNTERPARTY_RATIO_MIN:
        problems.append(
            f"ring/non-ring counterparty ratio {ratio:.2f}x < "
            f"{COUNTERPARTY_RATIO_MIN:.2f}x"
        )
    return _result(
        name,
        f"ring/non-ring counterparty ratio {ratio:.2f}x",
        problems,
        {
            "ring_avg": round(ring_avg, 4),
            "non_ring_avg": round(non_ring_avg, 4),
            "ratio": round(ratio, 4),
            "threshold": COUNTERPARTY_RATIO_MIN,
        },
    )
