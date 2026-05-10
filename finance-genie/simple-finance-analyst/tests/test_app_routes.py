from __future__ import annotations

import os

os.environ["USE_MOCK_BACKEND"] = "true"

from app import app


def test_search_rejects_missing_json_body() -> None:
    client = app.test_client()

    response = client.post("/api/search", data="not-json", content_type="text/plain")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be a JSON object."}


def test_search_rejects_invalid_filters() -> None:
    client = app.test_client()

    response = client.post(
        "/api/search",
        json={"signal_type": "fraud_rings", "filters": "bad"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "filters must be an object."}


def test_load_rejects_empty_ring_list() -> None:
    client = app.test_client()

    response = client.post("/api/load", json={"ring_ids": []})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "ring_ids must be a non-empty list of strings."
    }


def test_genie_rejects_blank_question() -> None:
    client = app.test_client()

    response = client.post("/api/genie", json={"question": "   "})

    assert response.status_code == 400
    assert response.get_json() == {"error": "question is required."}
