from __future__ import annotations

import json
import socket
import unittest
import urllib.error
from typing import cast
from unittest.mock import patch

from databricks.sdk import WorkspaceClient

from agentic_commerce.backend.demo_adapter import (
    adapt_diagnosis_trace,
    adapt_search_trace,
)
from agentic_commerce.backend.core._config import AppConfig
from agentic_commerce.backend.router import (
    DemoRouteError,
    _effective_user_id,
    _handle_search_failure,
    _log_demo_result,
    _safe_error_status,
)
from agentic_commerce.backend.models import AgenticSearchIn
from agentic_commerce.backend.sample_data import diagnosis_sample, search_sample
from agentic_commerce.backend.serving_client import (
    ServingInvocationError,
    invoke_retail_agent,
)


class _FakeWorkspaceClient:
    class _Config:
        host = "https://example.databricks.com"

        @staticmethod
        def authenticate() -> dict[str, str]:
            return {"Authorization": "Bearer token"}

    config = _Config()


class _FakeHTTPResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = json.dumps(body).encode("utf-8")
        self.headers = {"x-databricks-request-id": "dbx-request-1"}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class DemoAdapterTests(unittest.TestCase):
    def test_search_trace_maps_live_product_results(self) -> None:
        adapted = adapt_search_trace(
            {
                "messages": [{"role": "assistant", "content": "Pick these shoes."}],
                "custom_outputs": {
                    "demo_trace": {
                        "trace_source": "live",
                        "product_results": [
                            {
                                "product_id": "p1",
                                "name": "Logitech MX Master 3S",
                                "brand": "Logitech",
                                "price": 99.99,
                                "score": 0.94,
                            }
                        ],
                        "tool_timeline": [{"tool_name": "search_products"}],
                    }
                },
            }
        )

        self.assertEqual(adapted["trace_source"], "live")
        self.assertEqual(adapted["answer"], "Pick these shoes.")
        self.assertEqual(adapted["product_picks"][0].name, "Logitech MX Master 3S")
        self.assertEqual(adapted["tool_timeline"][0].tool_name, "search_products")

    def test_search_trace_preserves_tool_duration(self) -> None:
        adapted = adapt_search_trace(
            {
                "messages": [{"role": "assistant", "content": "Done."}],
                "custom_outputs": {
                    "demo_trace": {
                        "trace_source": "live",
                        "tool_timeline": [
                            {
                                "tool_name": "search_products",
                                "duration_ms": 237,
                            }
                        ],
                    }
                },
            }
        )

        self.assertEqual(adapted["tool_timeline"][0].duration_ms, 237)

    def test_search_trace_dedupes_products_and_uses_structured_summary(self) -> None:
        duplicate_id = "4:1cdf1524-084c-403c-b536-d2b8a273eec6:1899"
        adapted = adapt_search_trace(
            {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Here's what I found.\n\n"
                            "---\n\n"
                            "## Best picks\n\n"
                            "1. **Brooks Ghost 16** -- $140"
                        ),
                    }
                ],
                "custom_outputs": {
                    "demo_trace": {
                        "trace_source": "live",
                        "product_results": [
                            {
                                "product_id": duplicate_id,
                                "name": "Brooks Ghost 16",
                                "brand": "Brooks",
                                "price": 140,
                            },
                            {
                                "product_id": duplicate_id,
                                "name": "Brooks Ghost 16",
                                "brand": "Brooks",
                                "price": 140,
                            },
                            {
                                "product_id": "shoe-2",
                                "name": "Nike Pegasus 40",
                                "brand": "Nike",
                                "price": 130,
                            },
                        ],
                    }
                },
            }
        )

        self.assertEqual(len(adapted["product_picks"]), 2)
        self.assertEqual(
            adapted["summary"],
            "Found 2 live product picks: Brooks Ghost 16 and Nike Pegasus 40.",
        )

    def test_missing_demo_trace_degrades_to_prose(self) -> None:
        adapted = adapt_search_trace(
            {"messages": [{"role": "assistant", "content": "Plain answer."}]}
        )

        self.assertEqual(adapted["trace_source"], "unavailable")
        self.assertEqual(adapted["answer"], "Plain answer.")
        self.assertEqual(adapted["summary"], "Plain answer.")
        self.assertEqual(adapted["warnings"][0].code, "trace_unavailable")

    def test_diagnosis_trace_maps_chunks_to_actions_and_sources(self) -> None:
        adapted = adapt_diagnosis_trace(
            {
                "messages": [{"role": "assistant", "content": "Reset Bluetooth."}],
                "custom_outputs": {
                    "demo_trace": {
                        "knowledge_chunks": [
                            {
                                "chunk_id": "c1",
                                "text": "Calls drop when multipoint switches devices.",
                                "source_type": "SupportTicket",
                                "symptoms": ["disconnects during calls"],
                                "solutions": ["disable multipoint"],
                                "score": 0.9,
                            }
                        ],
                    }
                },
            }
        )

        self.assertEqual(adapted["trace_source"], "live")
        self.assertEqual(adapted["recommended_actions"][0].label, "disable multipoint")
        self.assertEqual(adapted["cited_sources"][0].id, "c1")

    def test_diagnosis_trace_uses_structured_summary(self) -> None:
        adapted = adapt_diagnosis_trace(
            {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            "Great news -- this is documented.\n\n"
                            "---\n\n"
                            "### Recommended Solutions\n\n"
                            "1. **Warranty Replacement**\n"
                            "2. **Shoe Goo Adhesive**"
                        ),
                    }
                ],
                "custom_outputs": {
                    "demo_trace": {
                        "knowledge_chunks": [
                            {
                                "chunk_id": "outsole-1",
                                "text": "Outsole delamination is commonly warranty-covered.",
                                "source_type": "KnowledgeArticle",
                                "solutions": [
                                    "Warranty replacement",
                                    "Apply Shoe Goo",
                                    "Avoid heat exposure",
                                ],
                            }
                        ],
                    }
                },
            }
        )

        self.assertEqual(
            adapted["summary"],
            "Found 1 relevant diagnosis source; recommended actions: "
            "Warranty replacement, Apply Shoe Goo, and Avoid heat exposure.",
        )


class SampleDataTests(unittest.TestCase):
    def test_search_sample_has_session_and_products(self) -> None:
        response = search_sample(
            preset_id="trail-running-shoes",
            prompt="trail shoes",
            request_id="req",
            session_id="session",
        )

        self.assertEqual(response.session_id, "session")
        self.assertEqual(response.source_type, "sample")
        self.assertTrue(response.product_picks)

    def test_diagnosis_sample_has_sources(self) -> None:
        response = diagnosis_sample(
            preset_id="outsole-peeling",
            prompt="outsole peeling",
            request_id="req",
            session_id="session",
        )

        self.assertEqual(response.trace_source, "sample")
        self.assertTrue(response.cited_sources)


class ErrorMappingTests(unittest.TestCase):
    def test_safe_error_status_does_not_leak_upstream_404(self) -> None:
        error = ServingInvocationError("missing", status_code=404)

        self.assertEqual(_safe_error_status(error), 502)

    def test_safe_error_status_maps_timeout(self) -> None:
        error = ServingInvocationError("timeout", status_code=504)

        self.assertEqual(_safe_error_status(error), 504)

    def test_effective_user_id_falls_back_to_session_id(self) -> None:
        self.assertEqual(_effective_user_id(None, "session-1"), "session:session-1")
        self.assertEqual(_effective_user_id("  ", "session-1"), "session:session-1")
        self.assertEqual(_effective_user_id("user-1", "session-1"), "user-1")

    def test_demo_result_log_contains_operational_fields(self) -> None:
        config = AppConfig(retail_agent_endpoint_name="endpoint-1")

        with self.assertLogs("agentic-commerce", level="INFO") as captured:
            _log_demo_result(
                mode="agentic_search",
                config=config,
                request_id="request-1",
                session_id="session-1",
                source_type="live",
                latency_ms=123,
                databricks_request_id="dbx-request-1",
                fallback_reason=None,
            )

        message = captured.output[0]
        self.assertIn("mode=agentic_search", message)
        self.assertIn("request_id=request-1", message)
        self.assertIn("session_id=session-1", message)
        self.assertIn("endpoint=endpoint-1", message)
        self.assertIn("source_type=live", message)
        self.assertIn("latency_ms=123", message)
        self.assertIn("databricks_request_id=dbx-request-1", message)

    def test_disabled_fallback_error_reports_unavailable(self) -> None:
        config = AppConfig(demo_allow_sample_fallback=False)
        request = AgenticSearchIn(prompt="trail shoes", session_id="session-1")
        error = ServingInvocationError(
            "offline",
            status_code=503,
            retryable=True,
            detail="Authorization: Bearer secret-token NEO4J_PASSWORD=secret-value",
        )

        with self.assertLogs("agentic-commerce", level="WARNING") as captured:
            with self.assertRaises(DemoRouteError) as raised:
                _handle_search_failure(
                    exc=error,
                    request=request,
                    config=config,
                    request_id="request-1",
                    session_id="session-1",
                    started=0.0,
                )

        self.assertFalse(raised.exception.error.fallback_available)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("demo_request_failed mode=agentic_search", captured.output[0])
        self.assertIn("status_code=503", captured.output[0])
        self.assertNotIn("secret-token", captured.output[0])
        self.assertNotIn("secret-value", captured.output[0])
        self.assertNotIn("secret-token", raised.exception.error.technical_detail or "")
        self.assertNotIn("secret-value", raised.exception.error.technical_detail or "")


class ServingClientTests(unittest.TestCase):
    def test_invoke_retail_agent_sends_custom_inputs(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            return _FakeHTTPResponse(
                {"messages": [{"role": "assistant", "content": "Live answer."}]}
            )

        config = AppConfig(retail_agent_timeout_seconds=17)
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = invoke_retail_agent(
                ws=cast(WorkspaceClient, _FakeWorkspaceClient()),
                config=config,
                prompt="Find trail shoes",
                session_id="session-1",
                user_id="user-1",
                demo_mode="agentic_search",
            )

        self.assertIn(config.retail_agent_endpoint_name, captured["url"])
        self.assertEqual(captured["timeout"], 17)
        self.assertEqual(
            captured["body"]["messages"],
            [{"role": "user", "content": "Find trail shoes"}],
        )
        self.assertEqual(
            captured["body"]["custom_inputs"],
            {
                "session_id": "session-1",
                "demo_mode": "agentic_search",
                "user_id": "user-1",
            },
        )
        self.assertEqual(result.databricks_request_id, "dbx-request-1")
        self.assertEqual(result.payload["messages"][0]["content"], "Live answer.")

    def test_invoke_retail_agent_maps_socket_timeout(self) -> None:
        config = AppConfig(retail_agent_timeout_seconds=1)
        with patch("urllib.request.urlopen", side_effect=socket.timeout("slow")):
            with self.assertRaises(ServingInvocationError) as raised:
                invoke_retail_agent(
                    ws=cast(WorkspaceClient, _FakeWorkspaceClient()),
                    config=config,
                    prompt="Find trail shoes",
                    session_id="session-1",
                    user_id="user-1",
                    demo_mode="agentic_search",
                )

        self.assertEqual(raised.exception.status_code, 504)
        self.assertTrue(raised.exception.retryable)

    def test_invoke_retail_agent_maps_wrapped_timeout(self) -> None:
        config = AppConfig(retail_agent_timeout_seconds=1)
        error = urllib.error.URLError(socket.timeout("slow"))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ServingInvocationError) as raised:
                invoke_retail_agent(
                    ws=cast(WorkspaceClient, _FakeWorkspaceClient()),
                    config=config,
                    prompt="Find trail shoes",
                    session_id="session-1",
                    user_id="user-1",
                    demo_mode="agentic_search",
                )

        self.assertEqual(raised.exception.status_code, 504)
        self.assertTrue(raised.exception.retryable)


if __name__ == "__main__":
    unittest.main()
