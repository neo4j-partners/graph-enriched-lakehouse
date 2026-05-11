from __future__ import annotations

from backend import RealBackend, _string_array


def test_string_array_decodes_databricks_connector_json_array() -> None:
    assert _string_array('["online","utilities","crypto"]') == [
        "online",
        "utilities",
        "crypto",
    ]


def test_fraud_ring_search_uses_latest_gold_summary_fields() -> None:
    backend = RealBackend()
    backend._gold_ring_summaries = lambda: [  # type: ignore[method-assign]
        {
            "ring_id": 17506,
            "node_count": 118,
            "volume": 214880.75,
            "shared_ids": ["crypto", "retail"],
            "risk_score": 2.5,
            "topology": "mesh",
        },
        {
            "ring_id": 16166,
            "node_count": 114,
            "volume": 98320,
            "shared_ids": ["online"],
            "risk_score": 1.25,
            "topology": "star",
        },
    ]
    backend._gold_graph_details_by_ring = lambda ring_ids, node_limit: {  # type: ignore[method-assign]
        "17506": {
            "nodes": [{"data": {"id": "a1", "risk_score": 2.5, "degree": 3}}],
            "edges": [],
        },
        "16166": {"nodes": [], "edges": []},
    }

    rings = backend.search("fraud_rings", {"max_nodes": 120})

    assert rings[0]["ring_id"] == "17506"
    assert rings[0]["node_count"] == 118
    assert rings[0]["volume"] == 214880
    assert rings[0]["shared_ids"] == ["crypto", "retail"]
    assert rings[0]["risk_score"] == 1.0
    assert rings[0]["raw_risk_score"] == 2.5
    assert rings[0]["risk_label"] == "High"
    assert rings[0]["topology"] == "mesh"
    assert rings[0]["nodes"] == [{"data": {"id": "a1", "risk_score": 2.5, "degree": 3}}]

    assert rings[1]["risk_score"] == 0.5
    assert rings[1]["risk_label"] == "Medium"
