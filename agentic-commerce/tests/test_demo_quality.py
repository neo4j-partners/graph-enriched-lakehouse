from __future__ import annotations

import unittest

from retail_agent.evaluation.demo_quality import (
    build_scorers,
    live_backend_contract,
    no_secret_leak,
    summarize_demo_response,
)


class DemoQualityTests(unittest.TestCase):
    def test_summarize_demo_response_counts_trace_fields(self) -> None:
        summary = summarize_demo_response(
            {
                "answer": "Use the waterproof trail runner.",
                "mode": "agentic_search",
                "source_type": "live",
                "trace_source": "live",
                "product_picks": [{"product_id": "shoe-1"}],
                "related_products": [{"product_id": "sock-1"}],
                "knowledge_chunks": [{"chunk_id": "chunk-1"}],
                "cited_sources": [{"title": "Care guide"}],
                "recommended_actions": [{"label": "Replace insoles"}],
                "memory_writes": [{"key": "preferred terrain"}],
                "tool_timeline": [{"tool": "recommend_for_user"}],
            },
            latency_ms=123,
        )

        self.assertEqual(summary["response"], "Use the waterproof trail runner.")
        self.assertEqual(summary["source_type"], "live")
        self.assertEqual(summary["trace_source"], "live")
        self.assertEqual(summary["product_count"], 1)
        self.assertEqual(summary["related_product_count"], 1)
        self.assertEqual(summary["knowledge_chunk_count"], 1)
        self.assertEqual(summary["cited_source_count"], 1)
        self.assertEqual(summary["recommended_action_count"], 1)
        self.assertEqual(summary["memory_write_count"], 1)
        self.assertEqual(summary["tool_timeline_count"], 1)
        self.assertEqual(summary["latency_ms"], 123)

    def test_live_backend_contract_requires_real_search_products(self) -> None:
        passed = live_backend_contract.run(
            inputs={"mode": "agentic_search"},
            outputs={
                "source_type": "live",
                "trace_source": "live",
                "product_count": 1,
            },
        )
        failed = live_backend_contract.run(
            inputs={"mode": "agentic_search"},
            outputs={
                "source_type": "sample",
                "trace_source": "static",
                "product_count": 1,
            },
        )

        self.assertTrue(passed.value)
        self.assertFalse(failed.value)

    def test_no_secret_leak_blocks_visible_credentials(self) -> None:
        clean = no_secret_leak.run(outputs={"response": "Try the trail runner."})
        leaked = no_secret_leak.run(
            outputs={"technical_detail": "Authorization: Bearer secret-token"}
        )

        self.assertTrue(clean.value)
        self.assertFalse(leaked.value)

    def test_default_scorers_are_deterministic_only(self) -> None:
        scorer_names = [scorer.name for scorer in build_scorers(False, None)]

        self.assertEqual(scorer_names, ["live_backend_contract", "no_secret_leak"])


if __name__ == "__main__":
    unittest.main()
