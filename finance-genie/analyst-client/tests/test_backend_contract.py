from __future__ import annotations

from typing import Any

from backend import RealBackend


class FakeSession:
    def __init__(self) -> None:
        self.params: dict[str, Any] | None = None
        self.cypher: str | None = None

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, _cypher: str, **params: Any) -> list[dict[str, Any]]:
        self.cypher = _cypher
        self.params = params
        return []


class FakeDriver:
    def __init__(self) -> None:
        self.session_instance = FakeSession()

    def session(self) -> FakeSession:
        return self.session_instance


def test_real_backend_search_accepts_null_frontend_filters() -> None:
    driver = FakeDriver()
    backend = RealBackend()
    backend._driver = lambda: driver  # type: ignore[method-assign]

    rings = backend.search(
        "fraud_rings",
        {"date_range": "Last 30 days", "min_amount": None, "max_nodes": None},
    )

    assert rings == []
    assert driver.session_instance.params == {
        "min_ring_size": 5,
        "ring_limit": 20,
        "node_limit": 80,
        "edge_limit": 240,
    }


def test_real_backend_search_defaults_invalid_numeric_filters() -> None:
    driver = FakeDriver()
    backend = RealBackend()
    backend._driver = lambda: driver  # type: ignore[method-assign]

    rings = backend.search("fraud_rings", {"max_nodes": "not-a-number"})

    assert rings == []
    assert driver.session_instance.params == {
        "min_ring_size": 5,
        "ring_limit": 20,
        "node_limit": 80,
        "edge_limit": 240,
    }


def test_real_backend_search_uses_max_nodes_as_bounded_payload_limit() -> None:
    driver = FakeDriver()
    backend = RealBackend()
    backend._driver = lambda: driver  # type: ignore[method-assign]

    rings = backend.search("fraud_rings", {"max_nodes": 25})

    assert rings == []
    assert driver.session_instance.params == {
        "min_ring_size": 5,
        "ring_limit": 20,
        "node_limit": 25,
        "edge_limit": 200,
    }


def test_fraud_rings_query_limits_before_fetching_ring_payloads() -> None:
    driver = FakeDriver()
    backend = RealBackend()
    backend._driver = lambda: driver  # type: ignore[method-assign]

    backend.search("fraud_rings", {})

    cypher = driver.session_instance.cypher or ""
    assert "collect(a) AS members" not in cypher
    assert "src IN members" not in cypher
    assert cypher.index("LIMIT $ring_limit") < cypher.index("CALL (ring_id)")


def test_search_queries_do_not_use_deprecated_internal_ids() -> None:
    driver = FakeDriver()
    backend = RealBackend()
    backend._driver = lambda: driver  # type: ignore[method-assign]

    backend.search("risk_scores", {})

    cypher = driver.session_instance.cypher or ""
    assert "id(a)" not in cypher
    assert "elementId(a)" in cypher
