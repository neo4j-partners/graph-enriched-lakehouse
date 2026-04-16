# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "neo4j>=5.20",
#     "python-dotenv>=1.0",
#     "graphdatascience>=1.12",
#     "pandas>=2.0",
# ]
# ///
"""Run the GDS pipeline from 02_aura_gds_guide against Neo4j Aura, then verify.

Mirrors the algorithm steps in feature_engineering/02_aura_gds_guide.ipynb so the
same PageRank / Louvain / Node Similarity calls run locally against Aura (no
Databricks involvement). Writes the same properties — risk_score, community_id,
similarity_score — and :SIMILAR_TO relationships that the notebook writes.

After the pipeline finishes, the script runs a diagnostic suite:

  1. Feature completeness    All three GDS properties set on every account
  2. PageRank separation     Top-20 fraud fraction; fraud/normal avg ratio
  3. Louvain ring coverage   For each ring, what community holds it, what fraction
                             of the community is fraud, is it a single community
  4. Node Similarity         :SIMILAR_TO count; fraud/normal avg ratio

Run from this directory:

    uv run run_and_verify_gds.py

This script WRITES to Neo4j (overwrites existing risk_score/community_id/
similarity_score properties and :SIMILAR_TO relationships), matching what the
notebook does. Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from graphdatascience import GraphDataScience
from neo4j.exceptions import AuthError, ServiceUnavailable

REQUIRED_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")

EXPECTED_ACCOUNTS = 25_000
TOP20_FRAUD_FRAC_MIN = 0.50
PR_RATIO_MIN = 2.0
COMMUNITY_PURITY_MIN = 0.50
SIM_RATIO_MIN = 2.0


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"FAIL  {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK    {msg}")


def header(label: str) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))


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


def drop_if_exists(gds: GraphDataScience, name: str) -> None:
    gds.run_cypher(f"CALL gds.graph.drop('{name}', false) YIELD graphName")


def run_pipeline(gds: GraphDataScience) -> None:
    header("Step 1: graph sanity")
    counts = gds.run_cypher(
        """
        MATCH (a:Account) WITH count(a) AS accounts
        MATCH (m:Merchant) WITH accounts, count(m) AS merchants
        MATCH ()-[t:TRANSACTED_WITH]->() WITH accounts, merchants, count(t) AS txns
        MATCH ()-[p:TRANSFERRED_TO]->() WITH accounts, merchants, txns, count(p) AS p2p
        RETURN accounts, merchants, txns, p2p
        """
    ).iloc[0]
    print(
        f"      accounts={counts['accounts']:,}  merchants={counts['merchants']:,}  "
        f"txns={counts['txns']:,}  p2p={counts['p2p']:,}"
    )
    if counts["accounts"] != EXPECTED_ACCOUNTS:
        fail(f"account count {counts['accounts']} != {EXPECTED_ACCOUNTS}")

    header("Step 2: project account_transfers (UNDIRECTED)")
    drop_if_exists(gds, "account_transfers")
    G, stats = gds.graph.project(
        "account_transfers",
        "Account",
        {"TRANSFERRED_TO": {"orientation": "UNDIRECTED"}},
    )
    print(
        f"      projected '{G.name()}': {stats['nodeCount']:,} nodes, "
        f"{stats['relationshipCount']:,} relationships"
    )

    header("Step 3: PageRank.write → risk_score")
    pr = gds.pageRank.write(
        G, maxIterations=20, dampingFactor=0.85, writeProperty="risk_score"
    )
    print(
        f"      propertiesWritten={int(pr['nodePropertiesWritten']):,}  "
        f"iterations={int(pr['ranIterations'])}  converged={bool(pr['didConverge'])}"
    )

    header("Step 4: Louvain.write → community_id")
    louvain = gds.louvain.write(G, writeProperty="community_id")
    print(
        f"      communityCount={int(louvain['communityCount']):,}  "
        f"modularity={float(louvain['modularity']):.4f}  "
        f"propertiesWritten={int(louvain['nodePropertiesWritten']):,}"
    )

    gds.graph.drop(G)

    header("Step 5: project account_merchants (NATURAL, bipartite)")
    drop_if_exists(gds, "account_merchants")
    G2, stats2 = gds.graph.project(
        "account_merchants",
        ["Account", "Merchant"],
        {"TRANSACTED_WITH": {"orientation": "NATURAL"}},
    )
    print(
        f"      projected '{G2.name()}': {stats2['nodeCount']:,} nodes, "
        f"{stats2['relationshipCount']:,} relationships"
    )

    header("Step 5.5: delete stale :SIMILAR_TO relationships")
    cleared = gds.run_cypher(
        "MATCH ()-[s:SIMILAR_TO]->() DELETE s RETURN count(*) AS deleted"
    )
    print(f"      deleted={int(cleared['deleted'].iloc[0]):,} stale relationships")

    header("Step 6: NodeSimilarity.write → :SIMILAR_TO + similarity_score")
    ns = gds.nodeSimilarity.write(
        G2,
        similarityMetric="JACCARD",
        topK=10,
        degreeCutoff=5,
        writeRelationshipType="SIMILAR_TO",
        writeProperty="similarity_score",
    )
    print(
        f"      nodesCompared={int(ns['nodesCompared']):,}  "
        f"relationshipsWritten={int(ns['relationshipsWritten']):,}"
    )
    gds.graph.drop(G2)

    header("Step 7: aggregate max similarity per account")
    agg = gds.run_cypher(
        """
        MATCH (a:Account)-[s:SIMILAR_TO]-()
        WITH a, MAX(s.similarity_score) AS max_sim
        SET a.similarity_score = max_sim
        RETURN count(a) AS accounts_updated
        """
    )
    print(f"      accounts_updated={int(agg['accounts_updated'].iloc[0]):,}")

    header("Step 8: set similarity_score=0 on accounts with no SIMILAR_TO edge")
    zeroed = gds.run_cypher(
        """
        MATCH (a:Account)
        WHERE NOT (a)-[:SIMILAR_TO]-()
        SET a.similarity_score = coalesce(a.similarity_score, 0.0)
        RETURN count(a) AS accounts_zeroed
        """
    )
    print(f"      accounts_zeroed={int(zeroed['accounts_zeroed'].iloc[0]):,}")


def check_feature_completeness(gds: GraphDataScience) -> list[str]:
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
    for name in ("has_pr", "has_cid", "has_sim"):
        label = {"has_pr": "risk_score", "has_cid": "community_id", "has_sim": "similarity_score"}[name]
        if int(row[name]) < int(row["total"]):
            problems.append(
                f"{label} set on only {int(row[name]):,}/{int(row['total']):,} accounts"
            )
    if not problems:
        ok("all three GDS features written on every account")
    return problems


def check_pagerank(gds: GraphDataScience, fraud_ids: list[int]) -> list[str]:
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
    print(
        f"      top-20 by risk_score: {top20_fraud}/20 are fraud "
        f"({top20_frac:.0%})"
    )

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
        f"      fraud avg = {fraud_avg:.4f}  normal avg = {normal_avg:.4f}  "
        f"ratio = {ratio:.2f}×"
    )

    if top20_frac < TOP20_FRAUD_FRAC_MIN:
        problems.append(
            f"top-20 fraud fraction {top20_frac:.0%} < {TOP20_FRAUD_FRAC_MIN:.0%}"
        )
    if ratio < PR_RATIO_MIN:
        problems.append(f"fraud/normal ratio {ratio:.2f}× < {PR_RATIO_MIN}×")
    if not problems:
        ok(f"PageRank: top-20 fraud {top20_frac:.0%}, ratio {ratio:.2f}×")
    return problems


def check_louvain_per_ring(gds: GraphDataScience, rings: list[dict]) -> list[str]:
    problems: list[str] = []

    # Community sizes
    sizes = gds.run_cypher(
        """
        MATCH (a:Account) WHERE a.community_id IS NOT NULL
        RETURN a.community_id AS cid, count(*) AS size
        """
    )
    cid_to_size = {int(r["cid"]): int(r["size"]) for _, r in sizes.iterrows()}
    n_communities = len(cid_to_size)
    print(f"      total communities: {n_communities:,}")

    total_ring_coverage = []
    purity_values = []
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
        avg_coverage = sum(total_ring_coverage) / len(total_ring_coverage) if total_ring_coverage else 0.0
        print(f"      avg community purity: {avg_purity:.0%}  avg ring coverage: {avg_coverage:.0%}")
        if avg_purity < COMMUNITY_PURITY_MIN:
            problems.append(
                f"avg Louvain purity {avg_purity:.0%} < {COMMUNITY_PURITY_MIN:.0%} — "
                f"communities absorbing too many non-fraud accounts"
            )
        elif not problems:
            ok(f"Louvain: avg purity {avg_purity:.0%} >= {COMMUNITY_PURITY_MIN:.0%}, avg coverage {avg_coverage:.0%}")
    return problems


def check_similarity(gds: GraphDataScience, fraud_ids: list[int]) -> list[str]:
    problems: list[str] = []
    row = gds.run_cypher(
        "MATCH ()-[s:SIMILAR_TO]->() RETURN count(s) AS n"
    ).iloc[0]
    n_sim = int(row["n"])
    print(f"      :SIMILAR_TO relationships: {n_sim:,}")
    if n_sim == 0:
        problems.append("no :SIMILAR_TO relationships written")
        return problems

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
        f"      fraud avg = {fraud_avg:.4f}  normal avg = {normal_avg:.4f}  "
        f"ratio = {ratio:.2f}×"
    )

    if ratio < SIM_RATIO_MIN:
        problems.append(f"fraud/normal similarity ratio {ratio:.2f}× < {SIM_RATIO_MIN}×")
    else:
        ok(f"Node Similarity: ratio {ratio:.2f}×")
    return problems


def main() -> None:
    script_dir = Path(__file__).parent
    env_path = script_dir / ".env"
    if not env_path.is_file():
        fail(f".env not found at {env_path}")
    load_dotenv(env_path, override=True)

    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        fail(f"missing in .env: {', '.join(missing)}")

    gt = load_ground_truth(script_dir)
    rings = gt["rings"]
    fraud_ids = [int(a) for r in rings for a in r["account_ids"]]
    ok(f"ground_truth.json loaded: {len(rings)} rings, {len(fraud_ids):,} fraud accounts")

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]

    gds = connect(uri, user, password)

    try:
        run_pipeline(gds)

        print()
        print("=" * 62)
        print("VERIFICATION")
        print("=" * 62)

        problems: list[str] = []

        header("[1/4] Feature completeness")
        problems += check_feature_completeness(gds)

        header("[2/4] PageRank (risk_score)")
        problems += check_pagerank(gds, fraud_ids)

        header("[3/4] Louvain (community_id) — per-ring coverage")
        problems += check_louvain_per_ring(gds, rings)

        header("[4/4] Node Similarity (similarity_score)")
        problems += check_similarity(gds, fraud_ids)

        print()
        if problems:
            print(f"FAIL  {len(problems)} problem(s):")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        print("PASS  GDS pipeline ran and outputs separate fraud from normal.")
    finally:
        try:
            gds.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
