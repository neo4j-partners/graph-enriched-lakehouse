"""Ring search service, backed by live Cypher against Aura.

Reads ring-candidate communities directly from Neo4j using the GDS node
properties written by enrichment-pipeline/setup/run_gds.py (`community_id` from
Louvain, `risk_score` from PageRank). One Cypher round-trip per call.

Shape parity with the previous SQL-backed version: same RingOut fields, same
order, so the frontend OpenAPI client requires no regeneration.
"""

from __future__ import annotations

from neo4j import Driver

from ..models import Graph, Risk, RingOut

# Minimum community size to count as a ring-candidate. Matches the
# enrichment-pipeline's is_ring_candidate gate (member_count >= 3).
_MIN_MEMBERS = 3

# Cap returned rings; mirrors the SQL LIMIT 20 from the previous gold-table
# query and keeps payloads small.
_TOP_N = 20


def _risk_band(score: float, max_score: float) -> Risk:
    normalized = score / max_score if max_score > 0 else 0.0
    if normalized >= 0.75:
        return "H"
    if normalized >= 0.5:
        return "M"
    return "L"


_RINGS_CYPHER = """
MATCH (a:Account)
WHERE a.community_id IS NOT NULL
WITH a.community_id AS community_id,
     count(a)       AS member_count,
     avg(a.risk_score) AS avg_risk_score
WHERE member_count >= $min_members AND member_count <= $max_nodes
OPTIONAL MATCH (b:Account)-[t:TRANSACTED_WITH]->(m:Merchant)
WHERE b.community_id = community_id
WITH community_id, member_count, avg_risk_score,
     collect(DISTINCT m.category) AS categories,
     sum(t.amount)                AS total_volume
RETURN community_id,
       member_count,
       avg_risk_score,
       categories[0..3] AS anchor_merchant_categories,
       coalesce(total_volume, 0)  AS total_volume_usd
ORDER BY avg_risk_score DESC
LIMIT $top_n
"""


def list_rings(driver: Driver, max_nodes: int) -> list[RingOut]:
    """Return up to 20 ring-candidate communities, ordered by avg_risk_score desc."""
    with driver.session() as session:
        rows = session.run(
            _RINGS_CYPHER,
            min_members=_MIN_MEMBERS,
            max_nodes=int(max_nodes),
            top_n=_TOP_N,
        ).data()

    if not rows:
        return []

    max_score = max((float(r.get("avg_risk_score") or 0) for r in rows), default=0.0)

    out: list[RingOut] = []
    for r in rows:
        risk_score = float(r.get("avg_risk_score") or 0)
        anchors = r.get("anchor_merchant_categories") or []
        if not isinstance(anchors, list):
            anchors = []

        out.append(
            RingOut(
                ring_id=str(r.get("community_id")),
                nodes=int(r.get("member_count") or 0),
                volume=int(float(r.get("total_volume_usd") or 0)),
                shared_identifiers=[str(a) for a in anchors],
                risk=_risk_band(risk_score, max_score),
                risk_score=risk_score,
                # Topology defaults to "mesh"; the UI computes its own layout
                # from id + node count + topology, so live classification is
                # not required for the demo.
                topology="mesh",
                graph=Graph(nodes=[], edges=[]),
            )
        )
    return out
