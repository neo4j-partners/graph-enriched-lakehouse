from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import Any

from retail_agent.agent.demo_trace import extract_demo_trace


@dataclass
class _AIMessage:
    tool_calls: list[dict[str, Any]]
    type: str = "ai"


@dataclass
class _ToolMessage:
    name: str | None
    tool_call_id: str
    content: Any
    status: str | None = "success"
    type: str = "tool"


class DemoTraceTests(unittest.TestCase):
    def test_recommend_for_user_becomes_product_results(self) -> None:
        trace = extract_demo_trace(
            [
                _AIMessage(
                    tool_calls=[
                        {
                            "name": "recommend_for_user",
                            "id": "call-1",
                            "args": {"query": "trail shoes"},
                        }
                    ]
                ),
                _ToolMessage(
                    name="recommend_for_user",
                    tool_call_id="call-1",
                    content=json.dumps(
                        {
                            "preferences_used": ["waterproof", "trail running"],
                            "recommendations": [
                                {
                                    "product_id": "shoe-1",
                                    "name": "Summit Trail Runner",
                                    "brand": "NeoTrail",
                                    "price": 129,
                                    "category": "Shoes",
                                    "relevance": 0.92,
                                    "supporting_context": [
                                        "Waterproof upper",
                                        "Trail outsole",
                                    ],
                                }
                            ],
                        }
                    ),
                ),
            ]
        )

        self.assertEqual(trace["trace_source"], "live")
        self.assertEqual(trace["product_results"][0]["product_id"], "shoe-1")
        self.assertEqual(trace["product_results"][0]["name"], "Summit Trail Runner")
        self.assertEqual(
            trace["profile"],
            [
                {"label": "preference", "value": "waterproof"},
                {"label": "preference", "value": "trail running"},
            ],
        )
        self.assertEqual(trace["tool_timeline"][1]["summary"]["recommendations"], 1)

    def test_non_json_tool_output_adds_warning(self) -> None:
        trace = extract_demo_trace(
            [
                _AIMessage(
                    tool_calls=[
                        {"name": "knowledge_search", "id": "call-1", "args": {}}
                    ]
                ),
                _ToolMessage(
                    name="knowledge_search",
                    tool_call_id="call-1",
                    content="plain text output",
                ),
            ]
        )

        self.assertEqual(trace["trace_source"], "live")
        self.assertEqual(trace["tool_timeline"][1]["content_type"], "text")
        self.assertIn("knowledge_search returned non-JSON output.", trace["warnings"])

    def test_tool_result_includes_timing_by_tool_call_id(self) -> None:
        trace = extract_demo_trace(
            [
                _AIMessage(
                    tool_calls=[
                        {
                            "name": "search_products",
                            "id": "call-1",
                            "args": {"query": "trail shoes"},
                        }
                    ]
                ),
                _ToolMessage(
                    name="search_products",
                    tool_call_id="call-1",
                    content=json.dumps({"products": [], "count": 0}),
                ),
            ],
            tool_timings=[
                {
                    "tool_name": "search_products",
                    "tool_call_id": "call-1",
                    "duration_ms": 237,
                }
            ],
        )

        self.assertEqual(trace["tool_timeline"][1]["duration_ms"], 237)

    def test_no_tool_events_adds_unavailable_warning(self) -> None:
        trace = extract_demo_trace([])

        self.assertEqual(trace["trace_source"], "unavailable")
        self.assertIn(
            "No LangGraph tool calls or tool results were captured.",
            trace["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
