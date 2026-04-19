# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "neo4j>=5.20",
#     "python-dotenv>=1.0",
#     "graphdatascience>=1.12",
#     "pandas>=2.0",
# ]
# ///
"""Verify GDS outputs against ground truth.

Run after run_gds.py completes. Connects to Neo4j, runs five signal checks,
and prints a summary report. Exits 0 if all checks pass, 1 if any fail.

Run from automated/:

    uv run validation/verify_gds.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from graphdatascience import GraphDataScience
from neo4j.exceptions import AuthError, ServiceUnavailable

from _common import fail, header, load_env, ok

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jobs"))
from gold_constants import (  # noqa: E402
    GDS_COMMUNITY_PURITY_MIN as COMMUNITY_PURITY_MIN,
    GDS_PR_RATIO_MIN as PR_RATIO_MIN,
    GDS_RING_EXCLUSION_MAX as RING_EXCLUSION_MAX,
    GDS_SIM_RATIO_MIN as SIM_RATIO_MIN,
)

REQUIRED_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
MAX_COMMUNITIES_OK = 500

# Must match the degreeCutoff used in run_gds.py.
NODESIM_DEGREE_CUTOFF = 5

# Summary table column widths
_LABEL_W = 38
_STATUS_W = 4


def load_ground_truth(script_dir: Path) -> dict:
    gt_path = script_dir.parent / "data" / "ground_truth.json"
    if not gt_path.is_file():
        fail(f"ground_truth.json not found at {gt_path}")
    return json.loads(gt_path.read_text())


def connect(uri: str, user: str, password: str) -> GraphDataScience:
    try:
        gds = GraphDataScience(uri, auth=(user, password))
        print(f"OK    connected  |  GDS client v{gds.version()}")
        return gds
    except AuthError as e:
        fail(f"authentication failed: {e}")
    except ServiceUnavailable as e:
        fail(f"cannot reach Neo4j at {uri}: {e}")
    except Exception as e:
        fail(f"GDS client error: {e}")


def check_feature_completeness(gds: GraphDataScience) -> tuple[list[str], str]:
    problems: list[str] = []
    row = gds.run_cypher(
        """
        MATCH (a:Account)
        RETURN count(a) AS total,
               sum(CASE WHEN a.risk_score       IS NOT NULL THEN 1 ELSE 0 END) AS has_pr,
               sum(CASE WHEN a.community_id     IS NOT NULL THEN 1 ELSE 0 END) AS has_cid,
               sum(CASE WHEN a.similarity_score IS NOT NULL THEN 1 ELSE 0 END) AS has_sim
        """
    ).iloc[0]
    print(
        f"      {row['total']:,} accounts | risk_score={row['has_pr']:,}  "
        f"community_id={row['has_cid']:,}  similarity_score={row['has_sim']:,}"
    )
    for name, label in (
        ("has_pr", "risk_score"),
        ("has_cid", "community_id"),
        ("has_sim", "similarity_score"),
    ):
        if int(row[name]) < int(row["total"]):
            problems.append(
                f"{label} set on only {int(row[name]):,}/{int(row['total']):,} accounts"
            )
    detail = "all 3 properties set" if not problems else f"{len(problems)} property gap(s)"
    return problems, detail


def check_pagerank(gds: GraphDataScience, fraud_ids: list[int]) -> tuple[list[str], str]:
    problems: list[str] = []
    stats = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN min(a.risk_score) AS mn, max(a.risk_score) AS mx,
               avg(a.risk_score) AS av
        """
    ).iloc[0]
    print(
        f"      risk_score: min={stats['mn']:.4f}  max={stats['mx']:.4f}  "
        f"avg={stats['av']:.4f}"
    )
    if stats["mx"] == stats["mn"]:
        problems.append("risk_score is constant — PageRank did not differentiate nodes")
        return problems, "constant (no signal)"

    top20 = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN a.account_id AS id, a.risk_score AS score
        ORDER BY a.risk_score DESC LIMIT 20
        """
    )
    fraud_set = set(fraud_ids)
    top20_fraud = sum(1 for i in top20["id"] if int(i) in fraud_set)
    top20_frac = top20_fraud / len(top20) if len(top20) else 0.0
    print(f"      top-20 by risk_score: {top20_fraud}/20 are fraud ({top20_frac:.0%})")

    averages = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN
          avg(CASE WHEN a.account_id IN $fraud_ids     THEN a.risk_score END) AS fraud_avg,
          avg(CASE WHEN NOT a.account_id IN $fraud_ids THEN a.risk_score END) AS normal_avg
        """,
        params={"fraud_ids": fraud_ids},
    ).iloc[0]
    fraud_avg = float(averages["fraud_avg"] or 0.0)
    normal_avg = float(averages["normal_avg"] or 0.0)
    ratio = fraud_avg / normal_avg if normal_avg else float("inf")
    print(
        f"      fraud avg={fraud_avg:.4f}  normal avg={normal_avg:.4f}  "
        f"ratio={ratio:.2f}×  (min {PR_RATIO_MIN}×)"
    )

    if ratio < PR_RATIO_MIN:
        problems.append(f"fraud/normal PageRank ratio {ratio:.2f}× < {PR_RATIO_MIN}×")
    return problems, f"ratio={ratio:.2f}×  (min {PR_RATIO_MIN}×)"


def check_louvain_per_ring(
    gds: GraphDataScience, rings: list[dict]
) -> tuple[list[str], str]:
    problems: list[str] = []

    sizes = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.community_id IS NOT NULL
        RETURN a.community_id AS cid, count(*) AS size
        """
    )
    cid_to_size = {int(r["cid"]): int(r["size"]) for _, r in sizes.iterrows()}
    n_communities = len(cid_to_size)
    print(f"      total communities: {n_communities:,}")

    if n_communities > MAX_COMMUNITIES_OK:
        problems.append(
            f"{n_communities:,} communities is excessive (>{MAX_COMMUNITIES_OK}). "
            f"Louvain fragmented the graph — indicates a sparse projection."
        )

    total_ring_coverage: list[float] = []
    purity_values: list[float] = []
    for ring in rings:
        ring_id = ring["ring_id"]
        members = [int(a) for a in ring["account_ids"]]

        cid_counts = gds.run_cypher(
            """
            MATCH (a:Account)
            WHERE a.account_id IN $members
            RETURN a.community_id AS cid, count(*) AS members_in_cid
            ORDER BY members_in_cid DESC
            """,
            params={"members": members},
        )
        if cid_counts.empty:
            problems.append(f"ring {ring_id}: no community_id set on any member")
            continue

        dominant_cid = int(cid_counts.iloc[0]["cid"])
        dominant_members = int(cid_counts.iloc[0]["members_in_cid"])
        coverage = dominant_members / len(members)
        dominant_size = cid_to_size.get(dominant_cid, 0)
        purity = dominant_members / dominant_size if dominant_size else 0.0
        distinct_cids = len(cid_counts)

        total_ring_coverage.append(coverage)
        purity_values.append(purity)
        print(
            f"      ring {ring_id}: {len(members)} members split across "
            f"{distinct_cids} communities | top cid={dominant_cid} "
            f"({dominant_members}/{len(members)} = {coverage:.0%} of ring, "
            f"purity {purity:.0%} of {dominant_size}-node community)"
        )

        if coverage < 0.80:
            problems.append(
                f"ring {ring_id}: only {coverage:.0%} of members in its dominant "
                f"community — Louvain is splitting the ring"
            )

    if purity_values:
        avg_purity = sum(purity_values) / len(purity_values)
        avg_coverage = (
            sum(total_ring_coverage) / len(total_ring_coverage)
            if total_ring_coverage
            else 0.0
        )
        print(
            f"      avg community purity: {avg_purity:.0%}  "
            f"avg ring coverage: {avg_coverage:.0%}  "
            f"(min purity {COMMUNITY_PURITY_MIN:.0%})"
        )
        if avg_purity < COMMUNITY_PURITY_MIN:
            problems.append(
                f"avg Louvain purity {avg_purity:.0%} < {COMMUNITY_PURITY_MIN:.0%} — "
                f"communities absorbing too many non-fraud accounts"
            )
        detail = f"purity={avg_purity:.0%}  coverage={avg_coverage:.0%}  (min purity {COMMUNITY_PURITY_MIN:.0%})"
    else:
        detail = "no rings found"
    return problems, detail


def check_similarity(
    gds: GraphDataScience, fraud_ids: list[int]
) -> tuple[list[str], str]:
    problems: list[str] = []
    row = gds.run_cypher(
        "MATCH ()-[s:SIMILAR_TO]->() RETURN count(s) AS n"
    ).iloc[0]
    n_sim = int(row["n"])
    print(f"      :SIMILAR_TO relationships: {n_sim:,}")
    if n_sim == 0:
        problems.append("no :SIMILAR_TO relationships written")
        return problems, "0 relationships"

    averages = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.similarity_score IS NOT NULL
        RETURN
          avg(CASE WHEN a.account_id IN $fraud_ids     THEN a.similarity_score END) AS fraud_avg,
          avg(CASE WHEN NOT a.account_id IN $fraud_ids THEN a.similarity_score END) AS normal_avg
        """,
        params={"fraud_ids": fraud_ids},
    ).iloc[0]
    fraud_avg = float(averages["fraud_avg"] or 0.0)
    normal_avg = float(averages["normal_avg"] or 0.0)
    ratio = fraud_avg / normal_avg if normal_avg else float("inf")
    print(
        f"      fraud avg={fraud_avg:.4f}  normal avg={normal_avg:.4f}  "
        f"ratio={ratio:.2f}×  (min {SIM_RATIO_MIN}×)"
    )

    if ratio < SIM_RATIO_MIN:
        problems.append(f"fraud/normal similarity ratio {ratio:.2f}× < {SIM_RATIO_MIN}×")
    return problems, f"ratio={ratio:.2f}×  (min {SIM_RATIO_MIN}×)"


def check_ring_member_nodesim_exclusion(
    gds: GraphDataScience, fraud_ids: list[int]
) -> tuple[list[str], str]:
    """Fraction of ring-member accounts excluded from the NodeSim bipartite
    projection by degreeCutoff. Ring members with fewer than the cutoff unique
    TRANSACTED_WITH targets carry similarity_score=0 but still land as
    fraud_risk_tier='high' via is_ring_community."""
    problems: list[str] = []

    row = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.account_id IN $fraud_ids
        OPTIONAL MATCH (a)-[:TRANSACTED_WITH]->(m:Merchant)
        WITH a, count(DISTINCT m) AS uniq_merchants
        RETURN count(a) AS total,
               sum(CASE WHEN uniq_merchants < $cutoff THEN 1 ELSE 0 END) AS excluded,
               avg(uniq_merchants) AS avg_uniq
        """,
        params={"fraud_ids": fraud_ids, "cutoff": NODESIM_DEGREE_CUTOFF},
    ).iloc[0]

    total = int(row["total"])
    excluded = int(row["excluded"])
    avg_uniq = float(row["avg_uniq"] or 0.0)
    frac = excluded / total if total else 0.0

    print(
        f"      ring members: {total:,}  "
        f"avg unique merchants: {avg_uniq:.1f}  "
        f"excluded at cutoff {NODESIM_DEGREE_CUTOFF}: {excluded:,} "
        f"({frac:.1%})  (max {RING_EXCLUSION_MAX:.0%})"
    )

    if frac > RING_EXCLUSION_MAX:
        problems.append(
            f"ring-member exclusion {frac:.1%} > {RING_EXCLUSION_MAX:.0%} "
            f"— similarity_score=0 coverage will drop below demo viability"
        )
    return problems, f"excluded={frac:.1%}  (max {RING_EXCLUSION_MAX:.0%})"


def print_summary(results: list[tuple[str, list[str], str]]) -> list[str]:
    W = 62
    all_problems: list[str] = []

    print()
    print("═" * W)
    print("VERIFICATION SUMMARY")
    print("═" * W)
    for label, problems, detail in results:
        status = "PASS" if not problems else "FAIL"
        print(f"  {label:<{_LABEL_W}}{status:<{_STATUS_W}}  {detail}")
        all_problems.extend(problems)
    print("─" * W)

    n_total = len(results)
    n_fail = sum(1 for _, p, _ in results if p)
    if all_problems:
        print(f"Result: FAIL  {n_fail}/{n_total} checks failed")
        print()
        for p in all_problems:
            print(f"  ✗ {p}")
    else:
        print(f"Result: PASS  {n_total}/{n_total} checks passed")
    print("═" * W)

    return all_problems


def main() -> None:
    load_env(REQUIRED_VARS)
    script_dir = Path(__file__).parent
    gt = load_ground_truth(script_dir)
    rings = gt["rings"]
    fraud_ids = [int(a) for r in rings for a in r["account_ids"]]
    ok(f"ground_truth.json loaded: {len(rings)} rings, {len(fraud_ids):,} fraud accounts")

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]

    gds = connect(uri, user, password)

    try:
        results: list[tuple[str, list[str], str]] = []

        header("[1/5] Feature completeness")
        problems, detail = check_feature_completeness(gds)
        results.append(("[1/5] Feature completeness", problems, detail))

        header("[2/5] PageRank (risk_score)")
        problems, detail = check_pagerank(gds, fraud_ids)
        results.append(("[2/5] PageRank (risk_score)", problems, detail))

        header("[3/5] Louvain (community_id) — per-ring coverage")
        problems, detail = check_louvain_per_ring(gds, rings)
        results.append(("[3/5] Louvain (community_id)", problems, detail))

        header("[4/5] Node Similarity (similarity_score)")
        problems, detail = check_similarity(gds, fraud_ids)
        results.append(("[4/5] Node Similarity", problems, detail))

        header("[5/5] Ring-member NodeSim exclusion (degreeCutoff)")
        problems, detail = check_ring_member_nodesim_exclusion(gds, fraud_ids)
        results.append(("[5/5] Ring-member exclusion", problems, detail))

        all_problems = print_summary(results)
        if all_problems:
            sys.exit(1)
    finally:
        try:
            gds.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
