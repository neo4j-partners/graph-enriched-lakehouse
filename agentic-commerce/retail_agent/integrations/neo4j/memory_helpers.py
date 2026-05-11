"""Shared helpers for user-scoped long-term memory operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neo4j_agent_memory import MemoryClient

logger = logging.getLogger(__name__)


async def store_user_preference(
    client: MemoryClient,
    user_id: str,
    category: str,
    preference: str,
    context: str | None = None,
) -> Any:
    """Store a preference scoped to a specific user.

    Returns the Preference object from the memory client.
    """
    return await client.long_term.add_preference(
        category=category,
        preference=preference,
        context=context,
        generate_embedding=True,
        user_identifier=user_id,
    )


async def get_user_preferences(
    client: MemoryClient,
    user_id: str,
    limit: int = 20,
) -> list[dict]:
    """Retrieve active preferences for a specific user.

    Returns a list of dicts with category, preference, context, confidence.
    """
    try:
        preferences = await client.long_term.get_preferences_for(user_id)
    except Exception as e:
        logger.warning("Failed to retrieve preferences for user %s: %s", user_id, e)
        return []

    results = []
    for pref in preferences[:limit]:
        results.append({
            "category": pref.category,
            "preference": pref.preference,
            "context": pref.context,
            "confidence": pref.confidence,
        })
    return results
