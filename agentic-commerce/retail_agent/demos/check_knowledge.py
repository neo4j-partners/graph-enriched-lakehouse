"""Verify the GraphRAG knowledge tools on the deployed agent endpoint.

Run after `retail-agent-demo` confirms the agent is healthy.
Exercises the three knowledge tools added in Phase 1 of EXPAND.md:

  1. knowledge_search          — semantic search + entity traversal
  2. hybrid_knowledge_search   — fulltext + vector + entity traversal
  3. diagnose_product_issue    — product-scoped symptom/solution lookup

Runs on a Databricks cluster or as a Databricks Job.
"""

import sys

from retail_agent.deployment.runtime import inject_env_params
from retail_agent.integrations.databricks.endpoint_client import ensure_endpoint_ready, run_exercise


def _run_knowledge_exercise(endpoint_url: str, headers: dict) -> tuple[int, int]:
    """Exercise GraphRAG knowledge tools with keyword validation."""
    turns = [
        (
            "My running shoes feel flat and unresponsive after 300 miles. What should I do?",
            "Knowledge search (troubleshooting)",
            ["foam", "replace"],
        ),
        (
            "Continental outsole peeling after 3 months of use",
            "Hybrid knowledge search (brand-specific term)",
            ["outsole"],
        ),
        (
            "What are the known issues and solutions for the nike-pegasus-40?",
            "Product diagnosis (GraphRAG)",
            ["pegasus"],
        ),
        (
            "Compare the cushioning issues between Nike Pegasus and Brooks Ghost",
            "Cross-product knowledge search",
            ["cushion"],
        ),
    ]
    return run_exercise(endpoint_url, headers, turns)


def check_knowledge() -> int:
    """Run GraphRAG knowledge tool checks against the deployed endpoint."""
    inject_env_params()

    try:
        endpoint_url, headers = ensure_endpoint_ready()
    except (RuntimeError, ValueError) as e:
        print(f"  Error: {e}")
        return 1

    print()
    print("Running knowledge exercise:")
    print("=" * 50)
    passed, failed = _run_knowledge_exercise(endpoint_url, headers)

    print()
    print(f"Knowledge exercise: {passed} passed, {failed} failed")
    print("Done.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(check_knowledge())
