"""Short-term memory tools using neo4j-agent-memory.

Session-scoped conversation store/recall and semantic search:
- remember_message: store a message in short-term memory with embeddings
- recall_memory: retrieve full conversation history
- search_memory: semantic similarity search via short_term.search_messages
"""

import json

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.agent.context import RetailContext


@tool
async def remember_message(
    content: str,
    role: str = "user",
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Store a message in short-term memory and return the conversation history.

    Use this tool when the user asks you to remember something, or when you
    want to save important information from the conversation. You can store
    both user messages and your own assistant responses.

    Args:
        content: The message content to store.
        role: Message role — 'user' for user messages, 'assistant' for your
            own responses. Storing both sides gives richer conversation recall.
    """
    client = runtime.context.client
    session_id = runtime.context.session_id or "default"
    user_identifier = runtime.context.memory_user_identifier

    await client.short_term.add_message(
        session_id,
        role,
        content,
        extract_entities=False,
        generate_embedding=True,
        user_identifier=user_identifier,
    )

    # Retrieve the conversation to confirm storage
    conversation = await client.short_term.get_conversation(session_id)
    messages = conversation.messages

    if not messages:
        return "Message stored, but no conversation history found."

    lines = [f"Stored message. Conversation has {len(messages)} message(s):"]
    for msg in messages:
        lines.append(f"  [{msg.role}] {msg.content}")
    return "\n".join(lines)


@tool
async def recall_memory(
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Retrieve the conversation history from short-term memory.

    Use this tool when the user asks what you remember, or to check
    what has been stored in memory.
    """
    client = runtime.context.client
    session_id = runtime.context.session_id or "default"

    conversation = await client.short_term.get_conversation(session_id)
    messages = conversation.messages

    if not messages:
        return "No messages found in memory."

    lines = [f"Found {len(messages)} message(s) in memory:"]
    for msg in messages:
        lines.append(f"  [{msg.role}] {msg.content}")
    return "\n".join(lines)


@tool
async def search_memory(
    query: str,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Search memory for relevant past conversations and facts using semantic similarity.

    Use this tool when the user asks about something specific from past conversations,
    or when you need to find relevant context without retrieving the full history.
    """
    client = runtime.context.client
    session_id = runtime.context.session_id or "default"
    messages = await client.short_term.search_messages(
        query, session_id=session_id, limit=5, threshold=0.5
    )

    results = []
    for msg in messages:
        results.append({
            "content": msg.content,
            "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
            "similarity": msg.metadata.get("similarity", 0.0),
        })

    return json.dumps({
        "query": query,
        "results": results,
        "count": len(results),
    })


# Flat tool list for import by retail_agent.agent.graph
MEMORY_TOOLS = [remember_message, recall_memory, search_memory]
