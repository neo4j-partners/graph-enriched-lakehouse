"""GraphRAG knowledge tools using ToolRuntime[RetailContext] injection.

Brings the retriever demo patterns into the live agent as direct Cypher
queries. No neo4j-graphrag dependency — all queries
run through client.graph.execute_read().

Three tools:
- knowledge_search: VectorCypher pattern (vector + entity traversal)
- hybrid_knowledge_search: Hybrid pattern (vector + fulltext + entity traversal)
- diagnose_product_issue: Product → Symptom → Solution graph traversal
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.agent.context import RetailContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def knowledge_search(
    query: str,
    limit: int = 5,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Search the knowledge base for support articles, reviews, and ticket resolutions using semantic search with entity-aware graph traversal.

    Use this tool when a customer asks about product issues, troubleshooting,
    how to fix something, or wants to understand product features and known
    problems. This searches knowledge articles, support tickets, and reviews
    — not the product catalog.
    """
    client = runtime.context.client
    embedder = runtime.context.embedder

    try:
        if embedder is None:
            raise RuntimeError("No embedder is configured.")
        embedding = await embedder.embed(query)
    except Exception as e:
        logger.warning("Embedding failed for knowledge_search: %s", e)
        return json.dumps({"error": "Embedding service unavailable", "detail": str(e)})

    # VectorCypher pattern: vector search on Chunk nodes, then traverse
    # MENTIONS_FEATURE / REPORTS_SYMPTOM / PROVIDES_SOLUTION entities,
    # and find related products through shared symptoms.
    cypher = """
    CALL db.index.vector.queryNodes('chunk_embedding', $limit, $embedding)
    YIELD node, score
    RETURN node.text AS text,
           node.chunk_id AS chunk_id,
           node.source_type AS source_type,
           score,
           collect { MATCH (node)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features,
           collect { MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS symptoms,
           collect { MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution) RETURN sol.name } AS solutions,
           collect {
               MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom)<-[:REPORTS_SYMPTOM]-(other:Chunk)
               WHERE other <> node
               MATCH (other)<-[:HAS_CHUNK]-(doc)-[:COVERS|ABOUT|REVIEWS]->(p:Product)
               RETURN DISTINCT p.name
           } AS related_products
    """
    params: dict[str, Any] = {"embedding": embedding, "limit": limit}

    try:
        result = await client.graph.execute_read(cypher, params)
    except Exception as e:
        logger.warning("Vector search failed in knowledge_search: %s", e)
        return json.dumps({"error": "Knowledge search failed", "detail": str(e)})

    items = [dict(r) for r in result]
    return json.dumps({"results": items, "count": len(items)})


@tool
async def hybrid_knowledge_search(
    query: str,
    limit: int = 5,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Search the knowledge base using both keyword matching and semantic similarity, with entity-aware graph traversal.

    Use this tool when the customer's question includes specific terminology
    (brand names, part names, technical terms) alongside a general question.
    Combines fulltext keyword search with vector similarity for better
    coverage, then traverses entity relationships for context.
    """
    client = runtime.context.client
    embedder = runtime.context.embedder

    try:
        if embedder is None:
            raise RuntimeError("No embedder is configured.")
        embedding = await embedder.embed(query)
    except Exception as e:
        logger.warning("Embedding failed for hybrid_knowledge_search: %s", e)
        return json.dumps({"error": "Embedding service unavailable", "detail": str(e)})

    # HybridCypher pattern: fulltext + vector search on Chunk nodes.
    # Scores are normalized per-index (divided by max in each result set)
    # before combining, following the neo4j-graphrag library convention.
    # Both indexes are limited to avoid unbounded result sets.
    cypher = """
    CALL db.index.fulltext.queryNodes('chunkText', $query, {limit: $candidate_limit})
    YIELD node AS ftNode, score AS ftScore
    WITH collect({node: ftNode, score: ftScore}) AS ftResults,
         max(ftScore) AS ftMax

    CALL db.index.vector.queryNodes('chunk_embedding', $candidate_limit, $embedding)
    YIELD node AS vecNode, score AS vecScore
    WITH ftResults, ftMax,
         collect({node: vecNode, score: vecScore}) AS vecResults,
         max(vecScore) AS vecMax

    WITH ftResults, ftMax, vecResults, vecMax
    UNWIND ftResults AS ft
    WITH vecResults, vecMax,
         collect({node: ft.node, score: CASE WHEN ftMax > 0 THEN ft.score / ftMax ELSE 0 END}) AS normFt
    UNWIND vecResults AS vec
    WITH normFt,
         collect({node: vec.node, score: CASE WHEN vecMax > 0 THEN vec.score / vecMax ELSE 0 END}) AS normVec

    UNWIND (normFt + normVec) AS item
    WITH item.node AS node, max(item.score) AS score
    ORDER BY score DESC
    LIMIT $limit

    RETURN node.text AS text,
           node.chunk_id AS chunk_id,
           node.source_type AS source_type,
           score,
           collect { MATCH (node)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features,
           collect { MATCH (node)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS symptoms,
           collect { MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution) RETURN sol.name } AS solutions,
           collect {
               MATCH (node)-[:PROVIDES_SOLUTION]->(sol:Solution)<-[:PROVIDES_SOLUTION]-(other:Chunk)
               WHERE other <> node
               MATCH (other)<-[:HAS_CHUNK]-(doc)-[:COVERS|ABOUT|REVIEWS]->(p:Product)
               RETURN DISTINCT p.name
           } AS products_with_same_solution
    """
    params: dict[str, Any] = {"query": query, "embedding": embedding, "limit": limit, "candidate_limit": limit * 2}

    try:
        result = await client.graph.execute_read(cypher, params)
    except Exception as e:
        logger.warning("Hybrid search failed in hybrid_knowledge_search: %s", e)
        return json.dumps({"error": "Hybrid knowledge search failed", "detail": str(e)})

    items = [dict(r) for r in result]
    return json.dumps({"results": items, "count": len(items)})


@tool
async def diagnose_product_issue(
    product_id: str,
    symptom_description: str | None = None,
    limit: int = 10,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Diagnose known issues for a specific product by traversing the knowledge graph for symptoms and solutions.

    Use this tool when a customer reports a problem with a specific product
    and you want to find known issues and recommended fixes. Optionally
    provide a symptom description to rank the most relevant symptoms first.
    """
    client = runtime.context.client
    embedder = runtime.context.embedder

    if symptom_description:
        # Embed the symptom description and use it to rank matching chunks
        # by similarity, then collect symptoms and solutions from those chunks.
        try:
            if embedder is None:
                raise RuntimeError("No embedder is configured.")
            embedding = await embedder.embed(symptom_description)
        except Exception as e:
            logger.warning("Embedding failed in diagnose_product_issue: %s", e)
            embedding = None

        if embedding is not None:
            cypher = """
            MATCH (p:Product)<-[:COVERS|ABOUT|REVIEWS]-(doc)-[:HAS_CHUNK]->(ch:Chunk)
            WHERE p.id = $product_id OR elementId(p) = $product_id
            WITH ch, vector.similarity.cosine(ch.embedding, $embedding) AS relevance
            WHERE relevance > 0.3
            ORDER BY relevance DESC
            LIMIT $limit
            RETURN ch.text AS context,
                   relevance,
                   collect { MATCH (ch)-[:REPORTS_SYMPTOM]->(s:Symptom) RETURN s.name } AS symptoms,
                   collect { MATCH (ch)-[:PROVIDES_SOLUTION]->(sol:Solution) RETURN sol.name } AS solutions,
                   collect { MATCH (ch)-[:MENTIONS_FEATURE]->(f:Feature) RETURN f.name } AS features
            """
            params: dict[str, Any] = {
                "product_id": product_id,
                "embedding": embedding,
                "limit": limit,
            }
        else:
            # Embedding failed — fall through to the non-embedding path
            symptom_description = None

    if not symptom_description:
        # No symptom description or embedding failed — return all known
        # symptoms and solutions for the product via direct graph traversal.
        cypher = """
        MATCH (p:Product)
        WHERE p.id = $product_id OR elementId(p) = $product_id
        OPTIONAL MATCH (p)-[:HAS_SYMPTOM]->(s:Symptom)
        OPTIONAL MATCH (p)-[:HAS_SOLUTION]->(sol:Solution)
        OPTIONAL MATCH (p)-[:HAS_FEATURE]->(f:Feature)
        WITH p,
             collect(DISTINCT s.name) AS symptoms,
             collect(DISTINCT sol.name) AS solutions,
             collect(DISTINCT f.name) AS features
        RETURN p.name AS product_name,
               p.id AS product_id,
               symptoms,
               solutions,
               features
        """
        params = {"product_id": product_id}

    try:
        result = await client.graph.execute_read(cypher, params)
    except Exception as e:
        logger.warning("Diagnose query failed: %s", e)
        return json.dumps({"error": "Diagnosis query failed", "detail": str(e)})

    if not result:
        return json.dumps({"error": "Product not found", "product_id": product_id})

    items = [dict(r) for r in result]
    return json.dumps({"product_id": product_id, "diagnosis": items})


# Flat tool list for import by retail_agent.agent.graph
KNOWLEDGE_TOOLS = [knowledge_search, hybrid_knowledge_search, diagnose_product_issue]
