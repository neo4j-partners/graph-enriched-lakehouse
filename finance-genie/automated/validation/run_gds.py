# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "neo4j>=5.20",
#     "python-dotenv>=1.0",
#     "graphdatascience>=1.12",
#     "pandas>=2.0",
# ]
# ///
"""Run the GDS pipeline against Neo4j Aura.

Mirrors the algorithm steps in workshop/02_aura_gds_guide.ipynb — writes
risk_score, betweenness_centrality, community_id, and similarity_score to every
:Account node, and creates :SIMILAR_TO relationships. Exits 0 on success, 1 on
failure.

Run from automated/:

    uv run validation/run_gds.py

Verify the outputs afterwards with:

    uv run validation/verify_gds.py
"""

from __future__ import annotations

import os

from graphdatascience import GraphDataScience
from neo4j.exceptions import AuthError, ServiceUnavailable

from _common import fail, header, load_env, ok

REQUIRED_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
EXPECTED_ACCOUNTS = 25_000

# NodeSimilarity degreeCutoff used in the pipeline below. Ring members whose
# unique TRANSACTED_WITH degree falls below this threshold are excluded from
# the bipartite projection and land with similarity_score=0. Keep this value
# synchronized with verify_gds.py and the writeRelationship call below.
NODESIM_DEGREE_CUTOFF = 5

# Exact betweenness is expensive on the 25k-node workshop graph. A fixed sample
# keeps demo runs predictable while preserving the "broker account" signal.
BETWEENNESS_SAMPLING_SIZE = 1_000
BETWEENNESS_SAMPLING_SEED = 42


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

    header("Step 4.5: Betweenness.write → betweenness_centrality")
    betweenness = gds.run_cypher(
        """
        CALL gds.betweenness.write($graph_name, {
          writeProperty: 'betweenness_centrality',
          samplingSize: $sampling_size,
          samplingSeed: $sampling_seed
        })
        YIELD nodePropertiesWritten, computeMillis, centralityDistribution
        RETURN nodePropertiesWritten, computeMillis,
               centralityDistribution.min AS min_score,
               centralityDistribution.mean AS mean_score,
               centralityDistribution.max AS max_score
        """,
        params={
            "graph_name": G.name(),
            "sampling_size": BETWEENNESS_SAMPLING_SIZE,
            "sampling_seed": BETWEENNESS_SAMPLING_SEED,
        },
    ).iloc[0]
    print(
        f"      propertiesWritten={int(betweenness['nodePropertiesWritten']):,}  "
        f"computeMillis={int(betweenness['computeMillis']):,}  "
        f"min={float(betweenness['min_score'] or 0.0):.4f}  "
        f"mean={float(betweenness['mean_score'] or 0.0):.4f}  "
        f"max={float(betweenness['max_score'] or 0.0):.4f}"
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
        degreeCutoff=NODESIM_DEGREE_CUTOFF,
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
        SET a.similarity_score = 0.0
        RETURN count(a) AS accounts_zeroed
        """
    )
    print(f"      accounts_zeroed={int(zeroed['accounts_zeroed'].iloc[0]):,}")


def main() -> None:
    load_env(REQUIRED_VARS)

    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]

    gds = connect(uri, user, password)

    try:
        run_pipeline(gds)
        ok("GDS pipeline complete — run verify_gds.py to check outputs")
    finally:
        try:
            gds.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
