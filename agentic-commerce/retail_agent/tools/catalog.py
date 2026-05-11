"""Product search and detail tools using ToolRuntime[RetailContext] injection.

Migrated from backend/tools/product_search.py — same Cypher queries and
business logic, but dependency injection replaces the closure factory.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.agent.context import RetailContext

logger = logging.getLogger(__name__)

ALLOWED_RELATIONSHIP_TYPES = frozenset({
    "IN_CATEGORY",
    "MADE_BY",
    "HAS_ATTRIBUTE",
    "BOUGHT_TOGETHER",
    "SIMILAR_TO",
})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def search_products(
    query: str,
    category: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    limit: int = 10,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Search the product catalog by query. Use this when a customer asks about products, wants to browse, or is looking for something specific."""
    client = runtime.context.client
    embedder = runtime.context.embedder
    conditions = ["p:Product"]
    params: dict[str, Any] = {"query": query, "limit": limit}

    if category:
        conditions.append("p.category = $category")
        params["category"] = category
    if brand:
        conditions.append("p.brand = $brand")
        params["brand"] = brand
    if max_price is not None:
        conditions.append("p.price <= $max_price")
        params["max_price"] = max_price

    where_clause = " AND ".join(conditions)

    try:
        if embedder is None:
            raise RuntimeError("No embedder is configured.")
        embedding = await embedder.embed(query)
        params["embedding"] = embedding

        cypher = f"""
        CALL db.index.vector.queryNodes('product_embedding', $limit, $embedding)
        YIELD node as p, score
        WHERE {where_clause}
        RETURN elementId(p) AS id, p.name AS name,
               coalesce(p.description, '') AS description,
               coalesce(p.price, 0) AS price,
               coalesce(p.category, '') AS category,
               coalesce(p.brand, '') AS brand,
               coalesce(p.in_stock, true) AS in_stock,
               score
        ORDER BY score DESC
        """
        result = await client.graph.execute_read(cypher, params)
    except Exception:
        logger.info("Vector search unavailable, falling back to text search")
        fallback_conditions = [
            "(toLower(p.name) CONTAINS toLower($query) "
            "OR toLower(coalesce(p.description, '')) CONTAINS toLower($query))"
        ]
        if category:
            fallback_conditions.append("p.category = $category")
        if brand:
            fallback_conditions.append("p.brand = $brand")
        if max_price is not None:
            fallback_conditions.append("p.price <= $max_price")
        fallback_where = " AND ".join(fallback_conditions)
        fallback_params = {
            key: value for key, value in params.items() if key != "embedding"
        }
        cypher = f"""
        MATCH (p:Product)
        WHERE {fallback_where}
        RETURN elementId(p) AS id, p.name AS name,
               coalesce(p.description, '') AS description,
               coalesce(p.price, 0) AS price,
               coalesce(p.category, '') AS category,
               coalesce(p.brand, '') AS brand,
               coalesce(p.in_stock, true) AS in_stock,
               1.0 AS score
        LIMIT $limit
        """
        result = await client.graph.execute_read(cypher, fallback_params)

    products = [dict(r) for r in result]
    return json.dumps({"products": products, "count": len(products)})


@tool
async def get_product_details(
    product_id: str,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Get full details for a specific product by ID. Use this when the customer wants to know more about a particular product."""
    client = runtime.context.client
    cypher = """
    MATCH (p:Product)
    WHERE elementId(p) = $product_id OR p.id = $product_id
    OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
    OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
    RETURN elementId(p) AS id, p.name AS name,
           coalesce(p.description, '') AS description,
           coalesce(p.price, 0) AS price,
           coalesce(c.name, p.category, '') AS category,
           coalesce(b.name, p.brand, '') AS brand,
           coalesce(p.in_stock, true) AS in_stock,
           coalesce(p.inventory, 0) AS inventory,
           p.image_url AS image_url
    """
    result = await client.graph.execute_read(cypher, {"product_id": product_id})
    if not result:
        return json.dumps({"error": "Product not found", "product_id": product_id})
    return json.dumps(dict(result[0]))


@tool
async def get_related_products(
    product_id: str,
    relationship_type: str | None = None,
    limit: int = 5,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Find products related to a given product through graph relationships. Use this for recommendations like 'what goes well with this' or 'similar items'."""
    client = runtime.context.client

    if relationship_type and relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
        return json.dumps({
            "error": f"Invalid relationship_type. Allowed: {sorted(ALLOWED_RELATIONSHIP_TYPES)}"
        })

    params: dict[str, Any] = {"product_id": product_id, "limit": limit}

    if relationship_type:
        cypher = f"""
        MATCH (p:Product)-[:{relationship_type}]->(shared)<-[:{relationship_type}]-(related:Product)
        WHERE (elementId(p) = $product_id OR p.id = $product_id)
        AND related <> p
        RETURN elementId(related) AS id, related.name AS name,
               coalesce(related.description, '')[..100] AS description,
               coalesce(related.price, 0) AS price,
               coalesce(related.category, '') AS category,
               coalesce(related.brand, '') AS brand,
               count(shared) AS shared_count
        ORDER BY shared_count DESC
        LIMIT $limit
        """
    else:
        cypher = """
        MATCH (p:Product)
        WHERE elementId(p) = $product_id OR p.id = $product_id
        CALL (p) {
            MATCH (p)-[:IN_CATEGORY]->(c)<-[:IN_CATEGORY]-(related:Product)
            WHERE related <> p
            RETURN related, 'category' as relation_type, c.name as shared
            UNION
            MATCH (p)-[:MADE_BY]->(b)<-[:MADE_BY]-(related:Product)
            WHERE related <> p
            RETURN related, 'brand' as relation_type, b.name as shared
            UNION
            MATCH (p)-[:HAS_ATTRIBUTE]->(a)<-[:HAS_ATTRIBUTE]-(related:Product)
            WHERE related <> p
            RETURN related, 'attribute' as relation_type, a.name as shared
        }
        WITH related,
             collect(DISTINCT {type: relation_type, value: shared}) AS connections
        RETURN elementId(related) AS id, related.name AS name,
               coalesce(related.description, '')[..100] AS description,
               coalesce(related.price, 0) AS price,
               coalesce(related.category, '') AS category,
               coalesce(related.brand, '') AS brand,
               size(connections) AS relevance_score
        ORDER BY relevance_score DESC
        LIMIT $limit
        """

    result = await client.graph.execute_read(cypher, params)
    related = [dict(r) for r in result]
    return json.dumps({"source_product_id": product_id, "related_products": related})


# Flat tool list for import by retail_agent.agent.graph
PRODUCT_SEARCH_TOOLS = [search_products, get_product_details, get_related_products]
