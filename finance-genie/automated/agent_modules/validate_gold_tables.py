"""Direct-SQL data-correctness gate for the gold tables.

Runs as a Databricks Python task. Reads the three gold tables written by
pull_gold_tables.py, joins them against ground_truth.json from the UC Volume,
and verifies that the fraud labels and ring aggregates align with the
simulated ground truth. Runs BEFORE genie_test.py so that a Genie test
failure can be distinguished from a bad gold-table build.

All joins against ground truth are keyed on account_id — never on the raw
community_id, which drifts across GDS runs.

Six checks:

  1. gold_fraud_ring_communities has exactly 10 rows with is_ring_candidate=true
  2. Each ring-candidate community is dominated by a single ground-truth ring:
     the dominant ring's members cover ≥80% of their home ring
  3. All ring-candidate communities have member_count BETWEEN 50 AND 200
  4. fraud_risk_tier='high' covers ≥ 75% of the 1,000 ring-member accounts
  5. For each ring-candidate community, top_account_id is a member of the
     dominant ring per ground_truth.json
  6. In gold_account_similarity_pairs, same_community=true holds for ≥ 95% of
     pairs where both accounts are in the same ring per ground_truth.json

Writes a JSON artifact to RESULTS_VOLUME_DIR. Exits non-zero on any failure.

Usage (from finance-genie/automated/ with .env in place):
    python -m cli upload --all
    python -m cli submit validate_gold_tables.py
    python -m cli logs
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1. Load .env extras forwarded by the runner as KEY=VALUE argv               #
# --------------------------------------------------------------------------- #
remaining: list[str] = []
for _arg in sys.argv[1:]:
    if "=" in _arg and not _arg.startswith("-"):
        _key, _, _val = _arg.partition("=")
        os.environ.setdefault(_key, _val)
    else:
        remaining.append(_arg)
sys.argv[1:] = remaining

# __file__ is not set when the cluster runs this via exec(compile(...));
# fall back to the frame's co_filename to find our sibling modules.
try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    import inspect as _inspect
    _HERE = Path(_inspect.currentframe().f_code.co_filename).resolve().parent
    del _inspect
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from gold_constants import (  # noqa: E402
    RING_SIZE_HIGH,
    RING_SIZE_LOW,
    TIER_HIGH,
)

# --------------------------------------------------------------------------- #
# 2. Config                                                                   #
# --------------------------------------------------------------------------- #
CATALOG = os.environ["CATALOG"]
SCHEMA = os.environ["SCHEMA"]
GROUND_TRUTH_PATH = os.environ["GROUND_TRUTH_PATH"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")

RING_CANDIDATE_COUNT_EXPECTED = 10
RING_DOMINANCE_MIN = 0.80
# RING_EXCLUSION_MAX=0.20 in run_and_verify_gds.py caps the fraction of ring
# members that the NodeSim bipartite projection excludes. Excluded members
# fall to fraud_risk_tier='medium' — so worst-case 'high' coverage is ~80%.
# 0.75 leaves 5% headroom over that cap while still catching real regressions.
HIGH_TIER_FRAC_MIN = 0.75
SAME_COMMUNITY_FRAC_MIN = 0.95

GOLD_ACCOUNTS = f"`{CATALOG}`.`{SCHEMA}`.gold_accounts"
GOLD_PAIRS = f"`{CATALOG}`.`{SCHEMA}`.gold_account_similarity_pairs"
GOLD_RINGS = f"`{CATALOG}`.`{SCHEMA}`.gold_fraud_ring_communities"


def header(label: str) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))


def load_ground_truth() -> dict:
    # UC Volumes are POSIX-accessible from Databricks Python tasks, so we can
    # open /Volumes/... directly instead of going through the Files API.
    try:
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FAIL  ground_truth not found at {GROUND_TRUTH_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"FAIL  ground_truth at {GROUND_TRUTH_PATH} is not valid JSON: {e}")
        sys.exit(1)


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    gt = load_ground_truth()
    rings = gt["rings"]
    ring_id_to_members: dict[int, set[int]] = {
        int(r["ring_id"]): {int(a) for a in r["account_ids"]} for r in rings
    }
    print(
        f"OK    ground_truth.json loaded: {len(rings)} rings, "
        f"{sum(len(m) for m in ring_id_to_members.values()):,} fraud accounts"
    )

    # One flat mapping of (account_id, ring_id) reused across checks 2, 4, 5, 6.
    ring_rows = [
        (int(a), int(rid))
        for rid, members in ring_id_to_members.items()
        for a in members
    ]
    ring_df = spark.createDataFrame(ring_rows, ["account_id", "ring_id"]).cache()

    ga_df = (
        spark.table(GOLD_ACCOUNTS)
        .select("account_id", "community_id", "fraud_risk_tier")
        .cache()
    )
    rc_df = (
        spark.table(GOLD_RINGS)
        .filter(F.col("is_ring_candidate"))
        .select("community_id", "member_count", "top_account_id")
        .cache()
    )

    problems: list[str] = []
    results: dict[str, dict] = {}
    try:
        problems += _run_checks(
            spark, ga_df, rc_df, ring_df, ring_id_to_members, results
        )
    finally:
        rc_df.unpersist()
        ga_df.unpersist()
        ring_df.unpersist()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    artifact_path = f"{RESULTS_VOLUME_DIR}/validate_gold_tables_{timestamp}.json"
    artifact = {
        "timestamp": timestamp,
        "catalog": CATALOG,
        "schema": SCHEMA,
        "problems": problems,
        "results": results,
    }
    try:
        Path(artifact_path).parent.mkdir(parents=True, exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)
        print(f"\nArtifact: {artifact_path}")
    except OSError as e:
        print(f"\nWARN  failed to write artifact to {artifact_path}: {e}")

    print()
    print("=" * 62)
    if problems:
        print(f"FAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("PASS  gold tables match ground truth (6/6).")


def _run_checks(
    spark,
    ga_df,
    rc_df,
    ring_df,
    ring_id_to_members: dict[int, set[int]],
    results: dict[str, dict],
) -> list[str]:
    problems: list[str] = []

    # ------------------------------------------------------------------- #
    # Check 1 — exactly 10 ring candidates                                #
    # ------------------------------------------------------------------- #
    header("[1/6] gold_fraud_ring_communities ring-candidate count")
    rc_count = rc_df.count()
    print(f"      is_ring_candidate=true: {rc_count}")
    results["ring_candidate_count"] = {
        "measured": rc_count,
        "expected": RING_CANDIDATE_COUNT_EXPECTED,
    }
    if rc_count == RING_CANDIDATE_COUNT_EXPECTED:
        print("OK    exactly 10 ring candidates")
    else:
        problems.append(
            f"ring_candidate_count = {rc_count}, expected {RING_CANDIDATE_COUNT_EXPECTED}"
        )

    # ------------------------------------------------------------------- #
    # Check 2 — each ring-candidate community dominated by one ring       #
    # Dominance = ring members in this community / total ring members.    #
    # Also builds community_to_ring for Check 5.                          #
    # ------------------------------------------------------------------- #
    header("[2/6] Each ring-candidate community ≥80% of its dominant ring")
    community_to_ring = _check_ring_dominance(
        rc_df, ga_df, ring_df, ring_id_to_members, results, problems
    )

    # ------------------------------------------------------------------- #
    # Check 3 — ring-candidate member_count BETWEEN 50 AND 200             #
    # Min/max and out-of-range count in a single aggregation.              #
    # ------------------------------------------------------------------- #
    header("[3/6] Ring-candidate member_count in [50, 200]")
    range_row = rc_df.agg(
        F.min("member_count").alias("min_size"),
        F.max("member_count").alias("max_size"),
        F.sum(
            F.when(
                ~F.col("member_count").between(RING_SIZE_LOW, RING_SIZE_HIGH),
                1,
            ).otherwise(0)
        ).alias("out_of_range"),
    ).collect()[0]
    out_of_range = int(range_row["out_of_range"] or 0)
    min_size = int(range_row["min_size"]) if range_row["min_size"] is not None else None
    max_size = int(range_row["max_size"]) if range_row["max_size"] is not None else None
    print(
        f"      member_count range: {min_size}–{max_size}  "
        f"out_of_range: {out_of_range}"
    )
    results["ring_size_range"] = {
        "low": RING_SIZE_LOW,
        "high": RING_SIZE_HIGH,
        "min": min_size,
        "max": max_size,
        "out_of_range": out_of_range,
    }
    if out_of_range:
        problems.append(
            f"{out_of_range} ring-candidate communities have member_count "
            f"outside [{RING_SIZE_LOW}, {RING_SIZE_HIGH}]"
        )
    else:
        print("OK    all ring candidates in range")

    # ------------------------------------------------------------------- #
    # Check 4 — fraud_risk_tier='high' covers ≥ 75% of ring members       #
    # ------------------------------------------------------------------- #
    header("[4/6] fraud_risk_tier='high' coverage of ring members")
    fraud_df = ring_df.select("account_id").distinct()
    tier_counts_row = (
        fraud_df.join(ga_df.select("account_id", "fraud_risk_tier"), "account_id", "left")
        .groupBy("fraud_risk_tier")
        .count()
        .collect()
    )
    tier_counts = {r["fraud_risk_tier"]: int(r["count"]) for r in tier_counts_row}
    total_ring_members = sum(tier_counts.values())
    high_count = tier_counts.get(TIER_HIGH, 0)
    high_frac = high_count / total_ring_members if total_ring_members else 0.0
    print(f"      ring members by tier: {tier_counts}")
    print(
        f"      fraud_risk_tier='high' coverage: {high_count}/{total_ring_members} "
        f"= {high_frac:.1%}"
    )
    results["high_tier_coverage"] = {
        "high_count": high_count,
        "total_ring_members": total_ring_members,
        "fraction": round(high_frac, 4),
        "threshold": HIGH_TIER_FRAC_MIN,
    }
    if high_frac >= HIGH_TIER_FRAC_MIN:
        print(f"OK    coverage {high_frac:.1%} >= {HIGH_TIER_FRAC_MIN:.0%}")
    else:
        problems.append(
            f"fraud_risk_tier='high' coverage {high_frac:.1%} < {HIGH_TIER_FRAC_MIN:.0%}"
        )

    # ------------------------------------------------------------------- #
    # Check 5 — top_account_id is a member of the dominant ring            #
    # ------------------------------------------------------------------- #
    header("[5/6] top_account_id belongs to the dominant ring")
    top_records = []
    for row in rc_df.select("community_id", "top_account_id").collect():
        cid = int(row["community_id"])
        top_id = (
            int(row["top_account_id"]) if row["top_account_id"] is not None else None
        )
        if top_id is None:
            problems.append(f"community {cid}: top_account_id is null")
            continue
        dominant_ring = community_to_ring.get(cid)
        if dominant_ring is None:
            # Check 2 already recorded the reason this community was skipped.
            continue
        in_ring = top_id in ring_id_to_members[dominant_ring]
        top_records.append(
            {
                "community_id": cid,
                "top_account_id": top_id,
                "dominant_ring": dominant_ring,
                "in_ring": in_ring,
            }
        )
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
    results["top_account_in_ring"] = top_records

    # ------------------------------------------------------------------- #
    # Check 6 — same_community=true for ≥95% of same-ring pairs           #
    # Single pass: count + sum(cast to int) in one aggregation.           #
    # ------------------------------------------------------------------- #
    header("[6/6] same_community=true holds for same-ring similarity pairs")
    pairs_with_rings = (
        spark.table(GOLD_PAIRS)
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
    pair_row = pairs_with_rings.agg(
        F.count("*").alias("total"),
        F.sum(F.col("same_community").cast("int")).alias("true_count"),
    ).collect()[0]
    same_ring_total = int(pair_row["total"] or 0)
    same_ring_true = int(pair_row["true_count"] or 0)
    same_ring_frac = same_ring_true / same_ring_total if same_ring_total else 0.0
    print(
        f"      same-ring pairs in gold_account_similarity_pairs: {same_ring_total:,}  "
        f"same_community=true: {same_ring_true:,} ({same_ring_frac:.1%})"
    )
    results["same_community_fraction"] = {
        "same_ring_total": same_ring_total,
        "same_community_true": same_ring_true,
        "fraction": round(same_ring_frac, 4),
        "threshold": SAME_COMMUNITY_FRAC_MIN,
    }
    if same_ring_total == 0:
        problems.append(
            "no same-ring pairs present in gold_account_similarity_pairs — "
            "Node Similarity did not produce intra-ring edges"
        )
    elif same_ring_frac >= SAME_COMMUNITY_FRAC_MIN:
        print(
            f"OK    same-ring fraction {same_ring_frac:.1%} >= "
            f"{SAME_COMMUNITY_FRAC_MIN:.0%}"
        )
    else:
        problems.append(
            f"same-ring same_community fraction {same_ring_frac:.1%} < "
            f"{SAME_COMMUNITY_FRAC_MIN:.0%}"
        )

    return problems


def _check_ring_dominance(
    rc_df,
    ga_df,
    ring_df,
    ring_id_to_members: dict[int, set[int]],
    results: dict[str, dict],
    problems: list[str],
) -> dict[int, int]:
    """Returns community_id → dominant ring_id for communities that passed the
    ring-lookup. Records problems for communities with no ring members or low
    dominance. Used by Check 5."""
    rc_members = (
        rc_df.select("community_id", "member_count")
        .join(ga_df.select("account_id", "community_id"), "community_id")
    )
    per_community = (
        rc_members.join(ring_df, "account_id", "left")
        .groupBy("community_id", "member_count")
        .agg(F.collect_list("ring_id").alias("ring_ids"))
    ).collect()

    community_to_ring: dict[int, int] = {}
    ring_to_community: dict[int, int] = {}
    dominance_records = []

    for r in per_community:
        cid = int(r["community_id"])
        member_count = int(r["member_count"])
        ring_ids = [int(x) for x in r["ring_ids"] if x is not None]
        if not ring_ids:
            problems.append(
                f"community {cid}: no ground-truth ring members in a "
                f"ring-candidate community"
            )
            continue
        counts: dict[int, int] = {}
        for rid in ring_ids:
            counts[rid] = counts.get(rid, 0) + 1
        dominant_ring, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        ring_size = len(ring_id_to_members[dominant_ring])
        dominance = dominant_count / ring_size
        community_to_ring[cid] = dominant_ring
        # Injectivity guard: two ring-candidate communities both dominated by
        # the same ring means Louvain split the ring — surface it cleanly.
        if dominant_ring in ring_to_community:
            problems.append(
                f"ring split: communities {ring_to_community[dominant_ring]} "
                f"and {cid} are both dominated by ring {dominant_ring}"
            )
        else:
            ring_to_community[dominant_ring] = cid
        dominance_records.append(
            {
                "community_id": cid,
                "member_count": member_count,
                "dominant_ring": dominant_ring,
                "ring_members_in_community": dominant_count,
                "ring_dominance": round(dominance, 3),
            }
        )
        print(
            f"      community {cid} (size {member_count}): dominant ring="
            f"{dominant_ring} ({dominant_count}/{ring_size} = {dominance:.0%})"
        )
        if dominance < RING_DOMINANCE_MIN:
            problems.append(
                f"community {cid}: dominant ring dominance {dominance:.0%} < "
                f"{RING_DOMINANCE_MIN:.0%}"
            )

    results["ring_dominance"] = dominance_records
    return community_to_ring


if __name__ == "__main__":
    main()
