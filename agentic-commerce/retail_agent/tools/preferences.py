"""Long-term preference tools using neo4j-agent-memory.

User-scoped preference storage and retrieval. Preferences persist across
sessions and are tied to user_id (not session_id):
- track_preference: store a user preference in long-term memory
- get_user_profile: retrieve all stored preferences for the current user
"""

import json
import logging

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.integrations.neo4j.memory_helpers import get_user_preferences, store_user_preference
from retail_agent.agent.context import RetailContext

logger = logging.getLogger(__name__)


@tool
async def track_preference(
    preference_type: str,
    preference_value: str,
    context: str | None = None,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Store a user preference in long-term memory for future personalization.

    Use this tool when the user expresses a preference such as a preferred
    brand, category, size, budget range, or activity type. Preferences persist
    across sessions and are used to personalize future recommendations.

    Args:
        preference_type: Category of preference (e.g. 'brand', 'category',
            'size', 'price_range', 'activity', 'material', 'style').
        preference_value: The preference itself (e.g. 'trail running',
            'waterproof', 'Nike', 'under $200', 'size 11').
        context: Optional context for when/where the preference applies.
    """
    client = runtime.context.client
    user_id = runtime.context.user_id

    if not user_id:
        return json.dumps({
            "error": "Cannot store preferences without a user_id. "
            "Preferences require a user identity to persist across sessions."
        })

    try:
        await store_user_preference(
            client=client,
            user_id=user_id,
            category=preference_type,
            preference=f"{preference_type}: {preference_value}",
            context=context,
        )
        return json.dumps({
            "stored": True,
            "preference_type": preference_type,
            "preference_value": preference_value,
            "user_id": user_id,
        })
    except Exception as e:
        logger.warning("Failed to store preference: %s", e)
        return json.dumps({"error": "Failed to store preference", "detail": str(e)})


@tool
async def get_user_profile(
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Retrieve the current user's stored preferences from long-term memory.

    Use this tool at the start of a session to understand the user's
    preferences, or mid-conversation when you need to check what you
    already know about them. Returns all stored preferences including
    brand, category, size, budget, and activity preferences.
    """
    client = runtime.context.client
    user_id = runtime.context.user_id

    if not user_id:
        return json.dumps({
            "preferences": [],
            "note": "No user_id provided — cannot retrieve long-term preferences.",
        })

    results = await get_user_preferences(client, user_id)

    return json.dumps({
        "user_id": user_id,
        "preferences": results,
        "count": len(results),
    })


# Flat tool list for import by retail_agent.agent.graph
PREFERENCE_TOOLS = [track_preference, get_user_profile]
