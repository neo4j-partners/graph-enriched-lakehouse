"""Focused checks for retail_agent demo trace extraction.

Run explicitly with:
    uv run pytest checks/demo_trace_check.py
"""

import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage


SRC_DIR = Path(__file__).resolve().parents[1] / "retail_agent" / "src"
sys.path.insert(0, str(SRC_DIR))

from demo_trace import extract_demo_trace, get_demo_mode_hint  # noqa: E402


def test_extracts_search_products_json():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_products",
                    "args": {"query": "running shoes", "limit": 2},
                    "id": "call-search",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "products": [
                        {
                            "id": "p1",
                            "name": "Trail Runner",
                            "price": 120,
                            "brand": "Acme",
                            "authorization": "hidden",
                        }
                    ],
                    "count": 1,
                }
            ),
            name="search_products",
            tool_call_id="call-search",
        ),
    ]

    trace = extract_demo_trace(messages)

    assert trace["trace_source"] == "live"
    assert trace["product_results"] == [
        {"id": "p1", "name": "Trail Runner", "price": 120, "brand": "Acme"}
    ]
    assert trace["tool_timeline"][0]["input_keys"] == ["limit", "query"]


def test_extracts_knowledge_search_and_diagnosis_json():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "knowledge_search",
                    "args": {"query": "headphones disconnect"},
                    "id": "call-knowledge",
                    "type": "tool_call",
                },
                {
                    "name": "diagnose_product_issue",
                    "args": {"product_id": "h1"},
                    "id": "call-diagnose",
                    "type": "tool_call",
                },
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "results": [
                        {
                            "chunk_id": "c1",
                            "text": "Bluetooth resets fix call drops.",
                            "source_type": "support_ticket",
                            "score": 0.91,
                            "features": ["Bluetooth"],
                            "symptoms": ["disconnect during calls"],
                            "solutions": ["reset pairing"],
                            "related_products": ["Travel Headphones"],
                        }
                    ],
                    "count": 1,
                }
            ),
            name="knowledge_search",
            tool_call_id="call-knowledge",
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "product_id": "h1",
                    "diagnosis": [
                        {
                            "product_name": "Travel Headphones",
                            "symptoms": ["disconnect during calls"],
                            "solutions": ["reset pairing"],
                            "features": ["Bluetooth"],
                        }
                    ],
                }
            ),
            name="diagnose_product_issue",
            tool_call_id="call-diagnose",
        ),
    ]

    trace = extract_demo_trace(messages)

    assert trace["knowledge_chunks"][0]["symptoms"] == ["disconnect during calls"]
    assert trace["knowledge_chunks"][0]["solutions"] == ["reset pairing"]
    assert trace["diagnosis"]["product_name"] == "Travel Headphones"
    assert trace["diagnosis"]["symptoms"] == ["disconnect during calls"]


def test_malformed_json_records_warning_without_failure():
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_products",
                    "args": {"query": "mouse"},
                    "id": "call-search",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="{not-json",
            name="search_products",
            tool_call_id="call-search",
        ),
    ]

    trace = extract_demo_trace(messages)

    assert trace["trace_source"] == "live"
    assert trace["product_results"] == []
    assert trace["tool_timeline"][1]["content_type"] == "text"
    assert trace["warnings"] == ["search_products returned non-JSON output."]


def test_no_tool_calls_returns_unavailable_trace():
    trace = extract_demo_trace([AIMessage(content="Plain assistant answer.")])

    assert trace["trace_source"] == "unavailable"
    assert trace["tool_timeline"] == []
    assert trace["product_results"] == []
    assert trace["warnings"] == [
        "No LangGraph tool calls or tool results were captured."
    ]


def test_supported_demo_mode_hints_only():
    assert "agentic_search" in get_demo_mode_hint("agentic_search")
    assert "issue_diagnosis" in get_demo_mode_hint("issue_diagnosis")
    assert get_demo_mode_hint("unsupported") is None
