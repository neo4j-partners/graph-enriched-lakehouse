"""LangGraph agent with echo tool and neo4j-agent-memory integration.

Builds on the base agent by adding:
- ToolRuntime[RetailContext] injection via context_schema
- Async memory tools backed by neo4j-agent-memory short-term memory
- The echo tool is retained for baseline validation

The agent uses create_react_agent with context_schema=RetailContext so
that ToolRuntime[RetailContext] parameters are injected automatically.
"""

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedToolArg
from pydantic import ConfigDict, Field, create_model
from pydantic_core import PydanticUndefined

from retail_agent.agent.config import CONFIG
from retail_agent.agent.context import RetailContext
from retail_agent.tools.commerce import COMMERCE_TOOLS
from retail_agent.tools.diagnostics import DIAGNOSTICS_TOOLS
from retail_agent.tools.knowledge import KNOWLEDGE_TOOLS
from retail_agent.tools.memory import MEMORY_TOOLS
from retail_agent.tools.preferences import PREFERENCE_TOOLS
from retail_agent.tools.catalog import PRODUCT_SEARCH_TOOLS
from retail_agent.tools.reasoning import REASONING_TOOLS


@tool
def echo(message: str) -> str:
    """Echo back the user's message. Use this tool to repeat what the user said."""
    return f"Echo: {message}"


SYSTEM_PROMPT = (
    "You are a retail product assistant with access to a Neo4j knowledge graph, "
    "long-term user memory, and reasoning trace capabilities. You can search "
    "products, diagnose issues, track user preferences, learn from past "
    "interactions, and provide personalized recommendations.\n\n"

    "SESSION START:\n"
    "- If a user_id is present, call get_user_profile at the start of the "
    "session to load stored preferences. Use this context to personalize all "
    "subsequent responses.\n\n"

    "TOOL SELECTION GUIDE:\n"
    "- For browsing, pricing, and catalog queries (e.g. 'show me running shoes "
    "under $150'), use search_products, get_product_details, get_related_products.\n"
    "- For support questions, troubleshooting, 'how do I fix', and product issue "
    "queries (e.g. 'my shoes feel flat', 'outsole peeling'), use knowledge_search "
    "or hybrid_knowledge_search.\n"
    "- When the query includes specific brand names or technical terms alongside a "
    "general question, prefer hybrid_knowledge_search over knowledge_search.\n"
    "- To find known issues and solutions for a specific product, use "
    "diagnose_product_issue with the product ID.\n\n"

    "PREFERENCES:\n"
    "- When the user expresses a preference (brand, category, size, budget, "
    "activity type, material, style), call track_preference to save it for "
    "future sessions.\n"
    "- Examples: 'I prefer Nike' -> track brand preference. 'My budget is "
    "under $200' -> track price_range preference. 'I need waterproof' -> "
    "track material preference.\n\n"

    "PERSONALIZED RECOMMENDATIONS:\n"
    "- When a user with stored preferences asks for recommendations, prefer "
    "recommend_for_user over raw product search. It combines their preference "
    "profile with knowledge graph traversal for better results.\n"
    "- If the user has no stored preferences, recommend_for_user falls back to "
    "standard knowledge search.\n\n"

    "REASONING TRACES:\n"
    "- When starting a multi-step task (product comparison, troubleshooting "
    "workflow, purchase recommendation), first call recall_past_reasoning to "
    "check if a similar task was handled before.\n"
    "- After completing a multi-step task, call record_reasoning_trace to log "
    "the approach, steps taken, and outcome for future learning.\n\n"

    "MEMORY:\n"
    "- Short-term memory (remember_message, recall_memory, search_memory) is "
    "for the current conversation session.\n"
    "- Long-term memory (track_preference, get_user_profile) persists across "
    "sessions and is tied to the user, not the session.\n"
    "- Reasoning traces (record_reasoning_trace, recall_past_reasoning) persist "
    "across sessions and help the agent learn from experience."
)

ALL_TOOLS = (
    [echo]
    + MEMORY_TOOLS
    + PREFERENCE_TOOLS
    + PRODUCT_SEARCH_TOOLS
    + KNOWLEDGE_TOOLS
    + REASONING_TOOLS
    + COMMERCE_TOOLS
    + DIAGNOSTICS_TOOLS
)


def _use_runtime_safe_args_schemas() -> None:
    """Keep runtime injectable without exposing complex objects to JSON schema."""
    for retail_tool in ALL_TOOLS:
        schema = retail_tool.get_input_schema()
        if "runtime" not in schema.model_fields:
            continue

        fields: dict[str, tuple[Any, Any]] = {}
        for name, field_info in schema.model_fields.items():
            annotation = field_info.annotation
            if name == "runtime":
                annotation = Annotated[Any, InjectedToolArg]

            if field_info.default_factory is not None:
                default = Field(
                    default_factory=field_info.default_factory,
                    description=field_info.description,
                )
            elif field_info.default is PydanticUndefined:
                default = Field(..., description=field_info.description)
            else:
                default = Field(
                    default=field_info.default,
                    description=field_info.description,
                )
            fields[name] = (annotation, default)

        retail_tool.args_schema = create_model(
            f"{retail_tool.name}_Args",
            __config__=ConfigDict(arbitrary_types_allowed=True),
            **fields,
        )


_use_runtime_safe_args_schemas()


def create_agent(llm=None):
    """Create a LangGraph ReAct agent with echo and memory tools.

    Args:
        llm: Optional LLM override. Defaults to ChatDatabricks with
             the endpoint configured in CONFIG.llm_endpoint.
    """
    from langgraph.prebuilt import create_react_agent

    if llm is None:
        from databricks_langchain import ChatDatabricks

        llm = ChatDatabricks(endpoint=CONFIG.llm_endpoint)

    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
        context_schema=RetailContext,
    )
