"""Direct-SQL data-correctness gate for the gold tables.

This runs as a Databricks Python task (not locally). It reads the three gold
tables written by pull_gold_tables.py, joins them against ground_truth.json
from the UC Volume, and verifies that the fraud labels and ring aggregates
align with the simulated ground truth. Runs BEFORE genie_test.py so that a
Genie test failure can be distinguished from a bad gold-table build.

All joins against ground truth are keyed on `account_id` — never on the raw
`community_id`, which drifts across GDS runs.

Six checks:

  1. gold_fraud_ring_communities has exactly 10 rows with is_ring_candidate=true
  2. Each ring-candidate community contains ≥ 80% of exactly one fraud ring's
     accounts (per ground_truth.json)
  3. All ring-candidate communities have member_count BETWEEN 50 AND 200
  4. fraud_risk_tier='high' covers ≥ 60% of the 1,000 ring-member accounts
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

import io
import json
import os
import sys
from datetime import datetime, timezone

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

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

# --------------------------------------------------------------------------- #
# 2. Config                                                                   #
# --------------------------------------------------------------------------- #
CATALOG = os.environ["CATALOG"]
SCHEMA = os.environ["SCHEMA"]
GROUND_TRUTH_PATH = os.environ["GROUND_TRUTH_PATH"]
RESULTS_VOLUME_DIR = os.environ["RESULTS_VOLUME_DIR"].rstrip("/")

RING_CANDIDATE_COUNT_EXPECTED = 10
RING_DOMINANCE_MIN = 0.80
MEMBER_COUNT_LOW = 50
MEMBER_COUNT_HIGH = 200
HIGH_TIER_FRAC_MIN = 0.60
SAME_COMMUNITY_FRAC_MIN = 0.95

GOLD_ACCOUNTS = f"`{CATALOG}`.`{SCHEMA}`.gold_accounts"
GOLD_PAIRS = f"`{CATALOG}`.`{SCHEMA}`.gold_account_similarity_pairs"
GOLD_RINGS = f"`{CATALOG}`.`{SCHEMA}`.gold_fraud_ring_communities"


def header(label: str) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))


def read_ground_truth() -> dict:
    ws = WorkspaceClient()
    volume_path = GROUND_TRUTH_PATH
    with io.BytesIO() as buf:
        download = ws.files.download(volume_path)
        buf.write(download.contents.read())
        raw = buf.getvalue()
    return json.loads(raw.decode("utf-8"))


def main() -> None:
    spark = SparkSession.builder.getOrCreate()

    gt = read_ground_truth()
    rings = gt["rings"]
    ring_id_to_members: dict[int, set[int]] = {
        int(r["ring_id"]): {int(a) for a in r["account_ids"]} for r in rings
    }
    fraud_ids = {a for members in ring_id_to_members.values() for a in members}
    print(
        f"OK    ground_truth.json loaded: {len(rings)} rings, "
        f"{len(fraud_ids):,} fraud accounts"
    )

    problems: list[str] = []
    results: dict[str, dict] = {}

    # ------------------------------------------------------------------- #
    # Check 1 — exactly 10 ring candidates                                #
    # ------------------------------------------------------------------- #
    header("[1/6] gold_fraud_ring_communities ring-candidate count")
    rc_df = spark.table(GOLD_RINGS).filter(F.col("is_ring_candidate"))
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
    # Check 2 — each ring-candidate community dominated by one ring ≥80%  #
    # ------------------------------------------------------------------- #
    header("[2/6] Each ring-candidate community ≥80% one ground-truth ring")
    ga_df = spark.table(GOLD_ACCOUNTS).select("account_id", "community_id")

    rc_members = (
        rc_df.select("community_id", "member_count")
        .join(ga_df, "community_id")
    )

    # Build (community_id, ring_id) rows from ground truth join.
    ring_rows = [
        (int(a), int(rid))
        for rid, members in ring_id_to_members.items()
        for a in members
    ]
    ring_df = spark.createDataFrame(ring_rows, ["account_id", "ring_id"])

    per_community = (
        rc_members.join(ring_df, "account_id", "left")
        .groupBy("community_id", "member_count")
        .agg(
            F.count(F.when(F.col("ring_id").isNotNull(), 1)).alias("fraud_members"),
            F.collect_list("ring_id").alias("ring_ids"),
        )
    )

    rows = per_community.collect()
    dominance_records = []
    ring_to_community: dict[int, int] = {}
    for r in rows:
        cid = int(r["community_id"])
        member_count = int(r["member_count"])
        ring_ids = [x for x in r["ring_ids"] if x is not None]
        if not ring_ids:
            problems.append(
                f"community {cid}: no ground-truth ring members in a ring-candidate community"
            )
            continue
        # Pick the dominant ring in this community.
        counts: dict[int, int] = {}
        for rid in ring_ids:
            counts[rid] = counts.get(rid, 0) + 1
        dominant_ring, dominant_count = max(counts.items(), key=lambda kv: kv[1])
        dominance = dominant_count / len(ring_id_to_members[dominant_ring])
        dominance_records.append(
            {
                "community_id": cid,
                "member_count": member_count,
                "dominant_ring": dominant_ring,
                "ring_members_in_community": dominant_count,
                "ring_dominance": round(dominance, 3),
            }
        )
        ring_to_community[dominant_ring] = cid
        print(
            f"      community {cid} (size {member_count}): dominant ring={dominant_ring} "
            f"({dominant_count}/{len(ring_id_to_members[dominant_ring])} = {dominance:.0%})"
        )
        if dominance < RING_DOMINANCE_MIN:
            problems.append(
                f"community {cid}: dominant ring dominance {dominance:.0%} < "
                f"{RING_DOMINANCE_MIN:.0%}"
            )
    results["ring_dominance"] = dominance_records

    # ------------------------------------------------------------------- #
    # Check 3 — ring-candidate member_count BETWEEN 50 AND 200             #
    # ------------------------------------------------------------------- #
    header("[3/6] Ring-candidate member_count in [50, 200]")
    out_of_range = (
        rc_df.filter(
            ~F.col("member_count").between(MEMBER_COUNT_LOW, MEMBER_COUNT_HIGH)
        )
        .select("community_id", "member_count")
        .collect()
    )
    if out_of_range:
        for r in out_of_range:
            problems.append(
                f"community {int(r['community_id'])} member_count "
                f"{int(r['member_count'])} outside [{MEMBER_COUNT_LOW},{MEMBER_COUNT_HIGH}]"
            )
    else:
        sizes = [int(r["member_count"]) for r in rc_df.select("member_count").collect()]
        sizes.sort()
        print(f"      member_count range: {sizes[0]}–{sizes[-1]} (all inside [50, 200])")
        print("OK    all ring candidates in range")
    results["ring_size_range"] = {
        "low": MEMBER_COUNT_LOW,
        "high": MEMBER_COUNT_HIGH,
        "out_of_range": len(out_of_range),
    }

    # ------------------------------------------------------------------- #
    # Check 4 — fraud_risk_tier='high' covers ≥ 60% of ring members       #
    # ------------------------------------------------------------------- #
    header("[4/6] fraud_risk_tier='high' coverage of ring members")
    fraud_df = spark.createDataFrame(
        [(a,) for a in sorted(fraud_ids)], ["account_id"]
    )
    tier_df = spark.table(GOLD_ACCOUNTS).select("account_id", "fraud_risk_tier")
    tier_counts_row = (
        fraud_df.join(tier_df, "account_id", "left")
        .groupBy("fraud_risk_tier")
        .count()
        .collect()
    )
    tier_counts = {r["fraud_risk_tier"]: int(r["count"]) for r in tier_counts_row}
    total_ring_members = sum(tier_counts.values())
    high_count = tier_counts.get("high", 0)
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
    rc_top_df = rc_df.select("community_id", "top_account_id").collect()
    top_records = []
    for r in rc_top_df:
        cid = int(r["community_id"])
        top_id = int(r["top_account_id"]) if r["top_account_id"] is not None else None
        if top_id is None:
            problems.append(f"community {cid}: top_account_id is null")
            continue
        dominant_ring = next(
            (rid for rid, c in ring_to_community.items() if c == cid), None
        )
        if dominant_ring is None:
            problems.append(
                f"community {cid}: no dominant ring mapping (Check 2 inconsistency)"
            )
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
    # ------------------------------------------------------------------- #
    header("[6/6] same_community=true holds for same-ring similarity pairs")
    pairs_df = spark.table(GOLD_PAIRS).select(
        "account_id_a", "account_id_b", "same_community"
    )
    # Join ring_id for both sides; keep only pairs where both accounts are
    # in the same ground-truth ring.
    pairs_with_rings = (
        pairs_df.join(
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
    same_ring_total = pairs_with_rings.count()
    same_ring_true = pairs_with_rings.filter(F.col("same_community")).count()
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

    # ------------------------------------------------------------------- #
    # Write artifact + summary                                            #
    # ------------------------------------------------------------------- #
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    artifact_path = f"{RESULTS_VOLUME_DIR}/validate_gold_tables_{timestamp}.json"
    artifact = {
        "timestamp": timestamp,
        "catalog": CATALOG,
        "schema": SCHEMA,
        "problems": problems,
        "results": results,
    }
    artifact_bytes = json.dumps(artifact, indent=2).encode("utf-8")
    try:
        ws = WorkspaceClient()
        ws.files.upload(artifact_path, io.BytesIO(artifact_bytes), overwrite=True)
        print(f"\nArtifact: {artifact_path}")
    except Exception as e:
        print(f"\nWARN  failed to write artifact to {artifact_path}: {e}")

    print()
    print("=" * 62)
    if problems:
        print(f"FAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("PASS  gold tables match ground truth (6/6).")


if __name__ == "__main__":
    main()
