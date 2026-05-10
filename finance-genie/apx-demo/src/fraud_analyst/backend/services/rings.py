"""Ring search service.

Reads ring-candidate communities from `gold_fraud_ring_communities` and shapes
them into `RingOut` records for Screen 1 of the workbench.
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem

from ..core._config import AppConfig
from ..models import Graph, Risk, RingOut, Topology
from . import sql


_VALID_TOPOLOGIES = {"star", "mesh", "chain"}


def _risk_band(score: float, max_score: float) -> Risk:
    """Map a normalized risk score in [0, 1] to a band.

    Louvain pageRank scores can run higher than 1.0, so we normalize against
    the column max before binning.
    """
    normalized = score / max_score if max_score > 0 else 0.0
    if normalized >= 0.75:
        return "H"
    if normalized >= 0.5:
        return "M"
    return "L"


def list_rings(ws: WorkspaceClient, config: AppConfig, max_nodes: int) -> list[RingOut]:
    """Return up to 20 ring-candidate communities ordered by avg_risk_score desc."""
    statement = f"""
        SELECT
          community_id,
          member_count,
          COALESCE(total_volume_usd, 0) AS total_volume_usd,
          COALESCE(avg_risk_score, 0) AS avg_risk_score,
          COALESCE(topology, 'mesh') AS topology,
          COALESCE(anchor_merchant_categories, ARRAY()) AS anchor_merchant_categories
        FROM `{config.catalog}`.`{config.schema_}`.gold_fraud_ring_communities
        WHERE is_ring_candidate = TRUE
          AND member_count <= :max_nodes
        ORDER BY avg_risk_score DESC
        LIMIT 20
    """
    parameters = [
        StatementParameterListItem(name="max_nodes", value=str(max_nodes), type="BIGINT"),
    ]
    rows = sql.execute(ws, config.warehouse_id, statement, parameters=parameters)

    if not rows:
        return []

    max_score = max((float(r.get("avg_risk_score") or 0) for r in rows), default=0.0)

    out: list[RingOut] = []
    for r in rows:
        risk_score = float(r.get("avg_risk_score") or 0)
        topology_raw = r.get("topology") or "mesh"
        topology: Topology = topology_raw if topology_raw in _VALID_TOPOLOGIES else "mesh"  # type: ignore[assignment]
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
                topology=topology,
                # UI computes layout client-side from id + nodes + topology, so
                # empty arrays are intentional.
                graph=Graph(nodes=[], edges=[]),
            )
        )
    return out
