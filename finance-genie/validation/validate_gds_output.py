# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "neo4j>=5.20",
#     "python-dotenv>=1.0",
# ]
# ///
"""Validate the GDS algorithm outputs written back to Neo4j Aura.

Checks that 02_aura_gds_guide produced meaningful features on :Account nodes
and that those features separate fraud ring members from normal accounts,
using ground_truth.json as the label source.

  1. Feature completeness  risk_score / community_id / similarity_score set on every account
  2. PageRank separation   top-20 by risk_score includes fraud members; fraud avg >> normal avg
  3. Louvain structure     ~10 tight communities with high fraud purity (not thousands of tiny ones)
  4. Node Similarity       SIMILAR_TO relationships exist; fraud avg similarity > normal avg

Run from this directory:

    uv run validate_gds_output.py

Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

REQUIRED_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")

EXPECTED_ACCOUNTS = 25_000

TOP20_FRAUD_FRAC_MIN = 0.50
PR_RATIO_MIN = 2.0
TIGHT_COMMUNITY_SIZE = 80
TIGHT_COMMUNITIES_MIN = 8
COMMUNITY_PURITY_MIN = 0.50
MAX_COMMUNITIES_OK = 500
SIM_RATIO_MIN = 2.0


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK    {msg}")


def load_ground_truth(script_dir: Path) -> tuple[set[int], int]:
    gt_path = script_dir.parent / "data" / "ground_truth.json"
    if not gt_path.is_file():
        fail(f"ground_truth.json not found at {gt_path}")
    gt = json.loads(gt_path.read_text())
    fraud_ids = {int(a) for r in gt["rings"] for a in r["account_ids"]}
    return fraud_ids, len(gt["rings"])


def connect(uri: str, user: str, password: str):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except AuthError as e:
        fail(f"authentication failed: {e}")
    except ServiceUnavailable as e:
        fail(f"cannot reach Neo4j at {uri}: {e}")
    except Exception as e:
        fail(f"driver error: {e}")


def check_feature_completeness(session) -> list[str]:
    problems: list[str] = []
    rec = session.run(
        """
        MATCH (a:Account)
        RETURN count(a) AS total,
               sum(CASE WHEN a.risk_score       IS NOT NULL THEN 1 ELSE 0 END) AS has_pr,
               sum(CASE WHEN a.community_id     IS NOT NULL THEN 1 ELSE 0 END) AS has_cid,
               sum(CASE WHEN a.similarity_score IS NOT NULL THEN 1 ELSE 0 END) AS has_sim
        """
    ).single()
    total, has_pr, has_cid, has_sim = (
        rec["total"],
        rec["has_pr"],
        rec["has_cid"],
        rec["has_sim"],
    )
    print(
        f"      {total:,} accounts | risk_score: {has_pr:,}  "
        f"community_id: {has_cid:,}  similarity_score: {has_sim:,}"
    )

    if total != EXPECTED_ACCOUNTS:
        problems.append(f"account count {total:,} != {EXPECTED_ACCOUNTS:,}")

    for name, got in [
        ("risk_score", has_pr),
        ("community_id", has_cid),
        ("similarity_score", has_sim),
    ]:
        if got == 0:
            problems.append(
                f"{name} is missing on every account — "
                f"02_aura_gds_guide did not run or did not writeProperty"
            )
        elif got < total:
            problems.append(
                f"{name} set on only {got:,}/{total:,} accounts — "
                f"GDS projection or writeback missed {total - got:,} accounts"
            )

    if not problems:
        ok("all three GDS features written on every account")
    return problems


def check_pagerank(session, fraud_ids: set[int]) -> list[str]:
    problems: list[str] = []

    stats = session.run(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN min(a.risk_score) AS mn, max(a.risk_score) AS mx,
               avg(a.risk_score) AS av
        """
    ).single()
    print(
        f"      risk_score: min={stats['mn']:.4f}  "
        f"max={stats['mx']:.4f}  avg={stats['av']:.4f}"
    )
    if stats["mx"] == stats["mn"]:
        problems.append("risk_score is constant — PageRank did not differentiate nodes")
        return problems

    top20 = session.run(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN a.account_id AS id, a.risk_score AS score
        ORDER BY a.risk_score DESC LIMIT 20
        """
    )
    top20_ids = [int(r["id"]) for r in top20]
    top20_fraud = sum(1 for i in top20_ids if i in fraud_ids)
    top20_frac = top20_fraud / len(top20_ids) if top20_ids else 0.0
    print(
        f"      top-20 by risk_score: {top20_fraud}/20 are fraud ring members "
        f"({top20_frac:.0%})"
    )

    averages = session.run(
        """
        MATCH (a:Account) WHERE a.risk_score IS NOT NULL
        RETURN
          avg(CASE WHEN a.account_id IN $fraud_ids     THEN a.risk_score END) AS fraud_avg,
          avg(CASE WHEN NOT a.account_id IN $fraud_ids THEN a.risk_score END) AS normal_avg
        """,
        fraud_ids=list(fraud_ids),
    ).single()
    fraud_avg = averages["fraud_avg"] or 0.0
    normal_avg = averages["normal_avg"] or 0.0
    ratio = fraud_avg / normal_avg if normal_avg else float("inf")
    print(
        f"      fraud avg risk_score = {fraud_avg:.4f}  "
        f"normal avg = {normal_avg:.4f}  ratio = {ratio:.2f}×"
    )

    if top20_frac < TOP20_FRAUD_FRAC_MIN:
        problems.append(
            f"top-20 fraud fraction {top20_frac:.0%} is below "
            f"{TOP20_FRAUD_FRAC_MIN:.0%}. PageRank is not elevating ring members. "
            f"Either the P2P graph is not ring-dense (check validate_neo4j_graph), "
            f"or PageRank is running on the wrong projection."
        )
    if ratio < PR_RATIO_MIN:
        problems.append(
            f"fraud/normal risk_score ratio {ratio:.2f}× is below {PR_RATIO_MIN}×. "
            f"PageRank does not separate fraud from normal."
        )
    if not problems:
        ok(
            f"PageRank: top-20 fraud = {top20_frac:.0%}, "
            f"fraud/normal ratio = {ratio:.2f}×"
        )
    return problems


def check_louvain(session, fraud_ids: set[int], expected_rings: int) -> list[str]:
    problems: list[str] = []

    sizes_res = session.run(
        """
        MATCH (a:Account) WHERE a.community_id IS NOT NULL
        RETURN a.community_id AS cid, count(*) AS size
        """
    )
    sizes = {int(r["cid"]): int(r["size"]) for r in sizes_res}
    n_communities = len(sizes)
    tight = {cid: sz for cid, sz in sizes.items() if sz >= TIGHT_COMMUNITY_SIZE}
    largest = sorted(sizes.values(), reverse=True)[:5]
    print(
        f"      {n_communities:,} communities total  "
        f"| tight (>= {TIGHT_COMMUNITY_SIZE}): {len(tight)}  "
        f"| largest 5: {largest}"
    )

    if n_communities > MAX_COMMUNITIES_OK:
        problems.append(
            f"{n_communities:,} communities is excessive (>{MAX_COMMUNITIES_OK}). "
            f"Louvain fragmented the graph — indicates a sparse projection. "
            f"Expected ~{expected_rings} large ring communities plus background noise."
        )

    if len(tight) < TIGHT_COMMUNITIES_MIN:
        problems.append(
            f"only {len(tight)} communities reach {TIGHT_COMMUNITY_SIZE}+ members, "
            f"expected >= {TIGHT_COMMUNITIES_MIN} (close to {expected_rings} rings). "
            f"Rings are not being resolved as single communities."
        )

    if tight:
        top_cids = sorted(tight.items(), key=lambda kv: kv[1], reverse=True)[:10]
        top_cid_list = [cid for cid, _ in top_cids]
        purity_res = session.run(
            """
            MATCH (a:Account)
            WHERE a.community_id IN $cids
            WITH a.community_id AS cid,
                 count(*) AS members,
                 sum(CASE WHEN a.account_id IN $fraud_ids THEN 1 ELSE 0 END) AS fraud_members
            RETURN cid, members, fraud_members
            """,
            cids=top_cid_list,
            fraud_ids=list(fraud_ids),
        )
        purities = []
        for r in purity_res:
            p = r["fraud_members"] / r["members"] if r["members"] else 0.0
            purities.append(p)
            print(
                f"      community {r['cid']}: {r['members']} members, "
                f"{r['fraud_members']} fraud ({p:.0%})"
            )
        avg_purity = sum(purities) / len(purities) if purities else 0.0
        if avg_purity < COMMUNITY_PURITY_MIN:
            problems.append(
                f"avg fraud purity of top-10 tight communities = {avg_purity:.0%}, "
                f"below {COMMUNITY_PURITY_MIN:.0%}. Louvain is grouping fraud "
                f"with non-fraud instead of isolating rings."
            )
        elif not problems:
            ok(
                f"Louvain: {len(tight)} tight communities, top-10 avg fraud purity "
                f"= {avg_purity:.0%}"
            )
    return problems


def check_similarity(session, fraud_ids: set[int]) -> list[str]:
    problems: list[str] = []

    rec = session.run(
        "MATCH ()-[s:SIMILAR_TO]->() RETURN count(s) AS n"
    ).single()
    n_sim = rec["n"]
    print(f"      :SIMILAR_TO relationships: {n_sim:,}")
    if n_sim == 0:
        problems.append("no :SIMILAR_TO relationships — Node Similarity did not write")
        return problems

    averages = session.run(
        """
        MATCH (a:Account) WHERE a.similarity_score IS NOT NULL
        RETURN
          avg(CASE WHEN a.account_id IN $fraud_ids     THEN a.similarity_score END) AS fraud_avg,
          avg(CASE WHEN NOT a.account_id IN $fraud_ids THEN a.similarity_score END) AS normal_avg
        """,
        fraud_ids=list(fraud_ids),
    ).single()
    fraud_avg = averages["fraud_avg"] or 0.0
    normal_avg = averages["normal_avg"] or 0.0
    ratio = fraud_avg / normal_avg if normal_avg else float("inf")
    print(
        f"      fraud avg similarity_score = {fraud_avg:.4f}  "
        f"normal avg = {normal_avg:.4f}  ratio = {ratio:.2f}×"
    )

    if ratio < SIM_RATIO_MIN:
        problems.append(
            f"fraud/normal similarity ratio {ratio:.2f}× is below {SIM_RATIO_MIN}×. "
            f"Node Similarity is not separating ring members from normal accounts."
        )
    else:
        ok(f"Node Similarity: fraud/normal ratio = {ratio:.2f}×")
    return problems


def main() -> None:
    script_dir = Path(__file__).parent
    env_path = script_dir / ".env"
    if not env_path.is_file():
        fail(f".env not found at {env_path}")
    load_dotenv(env_path, override=True)

    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        fail(f"missing or empty in .env: {', '.join(missing)}")

    fraud_ids, n_rings = load_ground_truth(script_dir)
    ok(f"ground_truth.json loaded: {n_rings} rings, {len(fraud_ids):,} fraud accounts")

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]

    driver = connect(uri, user, password)
    ok(f"connected to {uri}")

    problems: list[str] = []
    try:
        with driver.session() as session:
            print("\n[1/4] Feature completeness")
            problems += check_feature_completeness(session)

            print("\n[2/4] PageRank (risk_score)")
            problems += check_pagerank(session, fraud_ids)

            print("\n[3/4] Louvain (community_id)")
            problems += check_louvain(session, fraud_ids, n_rings)

            print("\n[4/4] Node Similarity (similarity_score)")
            problems += check_similarity(session, fraud_ids)
    finally:
        driver.close()

    print()
    if problems:
        print(f"FAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("PASS  GDS output is meaningful and separates fraud from normal.")


if __name__ == "__main__":
    main()
