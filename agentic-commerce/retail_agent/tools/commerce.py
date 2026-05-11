"""Agentic commerce tools using neo4j-agent-memory and GraphRAG.

Combines long-term user preferences with knowledge graph traversal for
personalized product recommendations:
- recommend_for_user: preference-aware product recommendations via VectorCypher
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.integrations.neo4j.memory_helpers import get_user_preferences
from retail_agent.agent.context import RetailContext

logger = logging.getLogger(__name__)


@tool
async def recommend_for_user(
    query: str | None = None,
    limit: int = 5,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Generate personalized product recommendations by combining the user's
    stored preference profile with knowledge graph traversal.

    Use this tool when a returning user asks for recommendations and has
    stored preferences. Combines their preferences (brand, category, activity,
    budget) with VectorCypher knowledge search for results grounded in both
    the user's history and the product knowledge graph.

    Falls back to a standard knowledge search if no user preferences exist.

    Args:
        query: Optional additional query to refine recommendations. If not
            provided, recommendations are based purely on stored preferences.
        limit: Maximum number of recommendations to return.
    """
    client = runtime.context.client
    embedder = runtime.context.embedder
    user_id = runtime.context.user_id

    # Step 1: Load user preferences from long-term memory
    preference_parts = []
    if user_id:
        user_prefs = await get_user_preferences(client, user_id)
        preference_parts = [p["preference"] for p in user_prefs]

    # Step 2: Build composite search query from preferences + explicit query
    query_parts = []
    if preference_parts:
        query_parts.append(" ".join(preference_parts))
    if query:
        query_parts.append(query)

    if not query_parts:
        return json.dumps({
            "recommendations": [],
            "note": "No preferences stored and no query provided. "
            "Ask the user what they are looking for, or use search_products instead.",
        })

    composite_query = " ".join(query_parts)

    # Step 3: Embed the composite query
    try:
        if embedder is None:
            raise RuntimeError("No embedder is configured.")
        embedding = await embedder.embed(composite_query)
    except Exception as e:
        logger.warning("Embedding failed for recommend_for_user: %s", e)
        return json.dumps({"error": "Embedding service unavailable", "detail": str(e)})

    # Step 4: VectorCypher search — find products through knowledge graph
    # traversal, scoring by relevance to the composite preference+query
    cypher = """
    CALL db.index.vector.queryNodes('chunk_embedding', $candidate_limit, $embedding)
    YIELD node, score
    OPTIONAL MATCH (node)<-[:HAS_CHUNK]-(doc)-[:COVERS|ABOUT|REVIEWS]->(p:Product)
    WHERE p IS NOT NULL
    WITH p, max(score) AS relevance,
         collect(DISTINCT node.text)[..2] AS supporting_context,
         collect { MATCH (node)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features,
         collect { MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS known_issues
    ORDER BY relevance DESC
    LIMIT $limit
    RETURN p.name AS name,
           p.id AS product_id,
           coalesce(p.price, 0) AS price,
           coalesce(p.category, '') AS category,
           coalesce(p.brand, '') AS brand,
           coalesce(p.description, '') AS description,
           relevance,
           supporting_context,
           features,
           known_issues
    """
    params: dict[str, Any] = {
        "embedding": embedding,
        "limit": limit,
        "candidate_limit": limit * 3,
    }

    try:
        result = await client.graph.execute_read(cypher, params)
    except Exception as e:
        logger.warning("Recommendation query failed: %s", e)
        return json.dumps({"error": "Recommendation search failed", "detail": str(e)})

    recommendations = [dict(r) for r in result]

    return json.dumps({
        "user_id": user_id,
        "preferences_used": preference_parts if preference_parts else None,
        "query": query,
        "recommendations": recommendations,
        "count": len(recommendations),
    })


# Flat tool list for import by retail_agent.agent.graph
COMMERCE_TOOLS = [recommend_for_user]
