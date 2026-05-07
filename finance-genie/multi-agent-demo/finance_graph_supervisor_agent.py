"""Neo4j GDS fraud specialist for the Finance Genie multi-agent demo."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator, Generator, Sequence
from typing import Annotated, Any, TypedDict

import mlflow
import nest_asyncio
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks, DatabricksMCPServer
from databricks_langchain import DatabricksMultiServerMCPClient
from langchain_core.language_models import LanguageModelLike
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)

nest_asyncio.apply()

LLM_ENDPOINT_NAME = os.environ.get(
    "LLM_ENDPOINT_NAME", "databricks-claude-sonnet-4-6"
)
UC_CONNECTION_NAME = os.environ.get("UC_CONNECTION_NAME", "neo4j_agentcore_mcp")
DATABRICKS_PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE") or os.environ.get(
    "DATABRICKS_PROFILE"
)

SYSTEM_PROMPT = """
You are Finance Neo4j GDS Fraud Specialist.

Your only data source is the Neo4j MCP server exposed through a Databricks
Unity Catalog external MCP connection. Do not answer by calling Genie, SQL
warehouses, Delta tables, or any non-graph tool.

Use Neo4j MCP tools to retrieve graph and GDS evidence for potential fraud-ring
candidates. Relevant evidence can include Account and Merchant nodes,
TRANSFERRED_TO, TRANSACTED_WITH, and SIMILAR_TO relationships, GDS-derived
properties such as risk_score, community_id, PageRank-style centrality,
Louvain-style community membership, node similarity, transfer density, and
shared merchant concentration.

When the user asks for likely fraud rings, return a compact supervisor-friendly
answer with:
- a short summary of the graph evidence;
- up to five candidate groups;
- capped account IDs for each candidate, preferably 5 to 20 IDs;
- the graph metrics or structural signals that made each candidate suspicious;
- a recommended downstream Genie prompt that asks the BEFORE Genie Space to
  analyze those account IDs against accounts, merchants, transactions, and
  account_links.

Use schema discovery before writing Cypher when graph structure is unclear.
If a discovery tool schema requires a properties argument but no filters are
needed, pass {"properties": {}}. Use only read-only graph queries. Never mutate
data. Never hardcode MCP tool names; choose tools from the discovered MCP tool
descriptions. Prefer aggregate answers and small examples over raw account
dumps.
"""


class AgentState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], add_messages]
    custom_inputs: dict[str, Any] | None
    custom_outputs: dict[str, Any] | None


def create_tool_calling_agent(
    model: LanguageModelLike,
    tools: ToolNode | Sequence[BaseTool],
    system_prompt: str | None = None,
):
    model = model.bind_tools(tools)

    def should_continue(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "continue"
        return "end"

    if system_prompt:
        preprocessor = RunnableLambda(
            lambda state: [{"role": "system", "content": system_prompt}]
            + state["messages"]
        )
    else:
        preprocessor = RunnableLambda(lambda state: state["messages"])

    model_runnable = preprocessor | model

    def call_model(
        state: AgentState, config: RunnableConfig
    ) -> dict[str, list[AnyMessage]]:
        response = model_runnable.invoke(state, config)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", RunnableLambda(call_model))
    workflow.add_node("tools", ToolNode(tools))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"continue": "tools", "end": END},
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile()


class LangGraphResponsesAgent(ResponsesAgent):
    def __init__(self, agent) -> None:
        self.agent = agent

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done" or event.type == "error"
        ]
        return ResponsesAgentResponse(output=outputs, custom_outputs=request.custom_inputs)

    async def _predict_stream_async(
        self,
        request: ResponsesAgentRequest,
    ) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
        cc_msgs = to_chat_completions_input([i.model_dump() for i in request.input])
        async for event in self.agent.astream(
            {"messages": cc_msgs},
            config={"recursion_limit": 24},
            stream_mode=["updates", "messages"],
        ):
            if event[0] == "updates":
                for node_data in event[1].values():
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, ToolMessage) and not isinstance(
                            msg.content, str
                        ):
                            msg.content = json.dumps(msg.content)
                    for item in output_to_responses_items_stream(messages):
                        yield item
            elif event[0] == "messages":
                chunk = event[1][0]
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    yield ResponsesAgentStreamEvent(
                        **self.create_text_delta(delta=chunk.content, item_id=chunk.id)
                    )

    def predict_stream(
        self,
        request: ResponsesAgentRequest,
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        agen = self._predict_stream_async(request)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        iterator = agen.__aiter__()
        while True:
            try:
                yield loop.run_until_complete(iterator.__anext__())
            except StopAsyncIteration:
                break


def initialize_agent() -> LangGraphResponsesAgent:
    workspace_client = (
        WorkspaceClient(profile=DATABRICKS_PROFILE)
        if DATABRICKS_PROFILE
        else WorkspaceClient()
    )
    host = workspace_client.config.host.rstrip("/")
    external_mcp_url = f"{host}/api/2.0/mcp/external/{UC_CONNECTION_NAME}"
    mcp_client = DatabricksMultiServerMCPClient(
        [
            DatabricksMCPServer(
                name="neo4j-gds-fraud-specialist",
                url=external_mcp_url,
                workspace_client=workspace_client,
            )
        ]
    )
    graph_tools = asyncio.run(mcp_client.get_tools())
    if not graph_tools:
        raise RuntimeError(f"No MCP tools discovered from {external_mcp_url}")

    llm = ChatDatabricks(
        endpoint=LLM_ENDPOINT_NAME,
        workspace_client=workspace_client,
    )
    return LangGraphResponsesAgent(
        create_tool_calling_agent(llm, graph_tools, SYSTEM_PROMPT)
    )


mlflow.langchain.autolog()
AGENT = initialize_agent()
mlflow.models.set_model(AGENT)
