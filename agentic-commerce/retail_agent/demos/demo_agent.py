"""Verify the deployed agent endpoint on Databricks.

Checks the endpoint exists, sends sample queries from CONFIG, and prints responses.
Uses raw REST calls (like aircraft_analyst) instead of the SDK's query() method,
which can have issues deserializing ChatAgent responses.

Exercises three memory layers:
  1. Short-term memory — session-scoped store/recall/search
  2. Long-term preferences — user-scoped preference tracking across sessions
  3. Sample queries — product search, lookup, and graph traversal (stateless)

Runs on a Databricks cluster or as a Databricks Job.
"""

import sys
from uuid import uuid4

import requests

from retail_agent.agent.config import CONFIG
from retail_agent.deployment.runtime import inject_env_params
from retail_agent.integrations.databricks.endpoint_client import (
    ensure_endpoint_ready,
    run_exercise,
    send_message,
)


# ---------------------------------------------------------------------------
# Exercise: Short-term memory (session-scoped)
# ---------------------------------------------------------------------------


def _run_memory_exercise(endpoint_url: str, headers: dict) -> tuple[int, int]:
    """Exercise short-term memory tools with a multi-turn conversation.

    Creates a unique session_id and sends a scripted conversation that tests:
    1. Storing facts via remember_message
    2. Recalling the full history via recall_memory
    3. Searching memory semantically via search_memory
    4. Using remembered context for recommendations
    """
    session_id = f"check-memory-{uuid4().hex[:8]}"
    custom_inputs = {"session_id": session_id}

    turns = [
        (
            "Remember that my name is Alex and I prefer trail running shoes.",
            "Store preferences",
            ["alex", "trail"],
        ),
        (
            "Remember that I wear size 11 and my budget is around $150.",
            "Store sizing/budget",
            ["size", "11"],
        ),
        (
            "What do you remember about me?",
            "Full recall",
            ["alex", "trail", "size", "11"],
        ),
        (
            "Search your memory for anything about my shoe preferences.",
            "Semantic memory search",
            ["trail", "running"],
        ),
        (
            "Based on what you know about me, recommend a product.",
            "Memory-based recommendation",
            ["trail", "running"],
        ),
    ]

    print(f"  Session ID: {session_id}")
    print(f"  Turns: {len(turns)}")
    return run_exercise(
        endpoint_url, headers, turns, custom_inputs,
        response_limit=300, accumulate_history=True,
    )


# ---------------------------------------------------------------------------
# Exercise: Long-term preferences (user-scoped, persists across sessions)
# ---------------------------------------------------------------------------


def _run_preference_exercise(endpoint_url: str, headers: dict) -> tuple[int, int]:
    """Exercise long-term preference tools with user_id scoping.

    Creates a unique user_id and session_id, then tests:
    1. Tracking preferences via track_preference (requires user_id)
    2. Retrieving stored preferences via get_user_profile
    3. Personalized recommendations via recommend_for_user
    """
    session_id = f"check-pref-{uuid4().hex[:8]}"
    user_id = f"demo-user-{uuid4().hex[:8]}"
    custom_inputs = {"session_id": session_id, "user_id": user_id}

    turns = [
        (
            "I prefer trail running shoes from Brooks.",
            "Track brand + activity preference",
            ["trail"],
        ),
        (
            "My budget is under $150 and I wear size 11.",
            "Track budget + size preference",
            ["150"],
        ),
        (
            "What are my stored preferences?",
            "Retrieve user profile",
            ["trail"],
        ),
        (
            "Based on my preferences, recommend a product for me.",
            "Preference-based recommendation",
            ["Brooks", "150"],
        ),
    ]

    print(f"  Session ID: {session_id}")
    print(f"  User ID: {user_id}")
    print(f"  Turns: {len(turns)}")
    return run_exercise(
        endpoint_url, headers, turns, custom_inputs,
        response_limit=300, accumulate_history=True,
    )


# ---------------------------------------------------------------------------
# Sample queries (stateless, isolated session)
# ---------------------------------------------------------------------------


def _run_sample_queries(endpoint_url: str, headers: dict) -> None:
    """Send stateless sample queries in an isolated session."""
    session_id = f"check-samples-{uuid4().hex[:8]}"
    custom_inputs = {"session_id": session_id}

    query_concepts = {
        "Echo hello world": "Basic connectivity",
        "Search for running shoes under $200": "Product search (Neo4j)",
        "Get details for product 'nike-pegasus-40'": "Product lookup (Neo4j)",
        "What products are related to 'brooks-ghost-16'?": "Graph traversal (Neo4j)",
    }

    for i, query in enumerate(CONFIG.sample_queries, 1):
        concept = query_concepts.get(query, "General")
        print(f"\n#### [{i}/{len(CONFIG.sample_queries)}] {concept}")
        print(f"Q: {query}")
        try:
            text = send_message(endpoint_url, headers, query, custom_inputs)
            if text:
                print(f"A: {text[:500]}")
            else:
                print("A: (no response text)")
        except requests.exceptions.HTTPError as e:
            print(f"Error: HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
        print(f"#### end {concept}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def check_endpoint() -> int:
    """Run basic checks against the deployed endpoint."""
    inject_env_params()

    try:
        endpoint_url, headers = ensure_endpoint_ready()
    except (RuntimeError, ValueError) as e:
        print(f"  Error: {e}")
        return 1

    print(f"  LLM endpoint: {CONFIG.llm_endpoint}")
    print(f"  Embedding model: {CONFIG.embedding_model}")

    # Run diagnostics check
    print()
    print("Running diagnostics:")
    print("-" * 40)
    try:
        text = send_message(
            endpoint_url, headers,
            "Run agent_diagnostics and return the raw JSON output only, no commentary.",
        )
        if text:
            print(text)
        else:
            print("(no response text)")
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    # Sample queries — stateless, isolated session
    print()
    print("Running sample queries:")
    print("=" * 50)
    _run_sample_queries(endpoint_url, headers)

    # Short-term memory exercise — session-scoped store/recall/search
    print()
    print("Running short-term memory exercise:")
    print("-" * 40)
    mem_passed, mem_failed = _run_memory_exercise(endpoint_url, headers)
    print(f"\nShort-term memory: {mem_passed} passed, {mem_failed} failed")

    # Long-term preference exercise — user-scoped preferences + recommendations
    print()
    print("Running long-term preference exercise:")
    print("-" * 40)
    pref_passed, pref_failed = _run_preference_exercise(endpoint_url, headers)
    print(f"\nLong-term preferences: {pref_passed} passed, {pref_failed} failed")

    total_passed = mem_passed + pref_passed
    total_failed = mem_failed + pref_failed
    print()
    print("=" * 50)
    print(f"Overall: {total_passed} passed, {total_failed} failed")
    print("Done.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(check_endpoint())
