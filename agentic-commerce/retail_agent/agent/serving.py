"""ChatAgent adapter for Databricks Model Serving.

Builds on the base agent by adding:
- Lazy MemoryClient init from secrets (NEO4J_URI, NEO4J_PASSWORD)
- Persistent event loop in a background thread for async bridging
- RetailContext injection into the LangGraph agent

References:
    - LANGCHAIN_AGENT.md Section 6 (ChatAgent adapter pattern)
    - neo4j-agent-memory integration
    - neo4j-agent-memory integrations/base.py (run_sync pattern)
"""

import asyncio
import os
import threading
import time
import traceback
from collections.abc import Mapping
from uuid import uuid4

import mlflow
from langchain_core.callbacks import BaseCallbackHandler
from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse

from retail_agent.agent.demo_trace import extract_demo_trace, get_demo_mode_hint


ALLOW_UNINITIALIZED_ENV = "RETAIL_AGENT_ALLOW_UNINITIALIZED_FOR_LOGGING"


def _allow_uninitialized_for_logging() -> bool:
    value = os.environ.get(ALLOW_UNINITIALIZED_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _create_background_loop() -> asyncio.AbstractEventLoop:
    """Create a persistent event loop running in a background thread.

    This avoids the "async driver bound to wrong event loop" problem:
    asyncio.run() creates and destroys a new loop each time, but the
    Neo4j async driver is bound to the loop it was connected on. By
    keeping one loop alive, all async work (connect, tool calls, etc.)
    runs on the same loop across requests.
    """
    loop = asyncio.new_event_loop()

    def _run(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=_run, args=(loop,), daemon=True)
    thread.start()
    return loop


class ToolTimingCallback(BaseCallbackHandler):
    """Collect per-tool latency for the demo metadata contract."""

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._completed: list[dict[str, object]] = []

    @property
    def completed(self) -> list[dict[str, object]]:
        return list(self._completed)

    def on_tool_start(
        self,
        serialized: dict[str, object],
        input_str: str,
        *,
        run_id,
        **kwargs,
    ) -> None:
        run_key = str(run_id)
        self._starts[run_key] = time.perf_counter()
        tool_name = _tool_name_from_serialized(serialized)
        if tool_name:
            self._tool_names[run_key] = tool_name

    def on_tool_end(self, output: object, *, run_id, **kwargs) -> None:
        self._record_completion(run_id, output=output, status="success")

    def on_tool_error(self, error: BaseException, *, run_id, **kwargs) -> None:
        self._record_completion(run_id, output=None, status="error")

    def _record_completion(
        self,
        run_id,
        *,
        output: object,
        status: str,
    ) -> None:
        run_key = str(run_id)
        started = self._starts.pop(run_key, None)
        if started is None:
            return

        item: dict[str, object] = {
            "duration_ms": max(1, int((time.perf_counter() - started) * 1000)),
            "status": status,
        }
        tool_name = self._tool_names.pop(run_key, None)
        if tool_name:
            item["tool_name"] = tool_name

        tool_call_id = getattr(output, "tool_call_id", None)
        if isinstance(tool_call_id, str) and tool_call_id:
            item["tool_call_id"] = tool_call_id
        self._completed.append(item)


def _tool_name_from_serialized(serialized: Mapping[str, object]) -> str | None:
    name = serialized.get("name")
    if isinstance(name, str) and name:
        return name

    kwargs = serialized.get("kwargs")
    if isinstance(kwargs, Mapping):
        kwargs_name = kwargs.get("name")
        if isinstance(kwargs_name, str) and kwargs_name:
            return kwargs_name

    return None


class RetailAgent(ChatAgent):
    """ChatAgent adapter with Neo4j memory integration."""

    def __init__(self):
        # All attributes must be defined in __init__ (MLflow requirement)
        self._agent = None
        self._initialized = False
        self._init_error: str | None = None
        self._client = None
        self._embedder = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_initialized(self):
        """Lazy initialization of agent and MemoryClient.

        Follows the aircraft_analyst pattern: catches all exceptions and
        stores them in _init_error rather than crashing. predict() checks
        _init_error and returns an error message to the caller.

        During log_model() validation, secrets aren't available — we detect
        this and skip init so predict() can return a placeholder response.
        """
        if self._initialized:
            return

        # Secrets are intentionally unavailable during model logging and
        # validation. Serving must provide them through endpoint env vars.
        if "NEO4J_URI" not in os.environ or "NEO4J_PASSWORD" not in os.environ:
            return

        try:
            from neo4j_agent_memory import (
                EmbeddingConfig,
                ExtractionConfig,
                ExtractorType,
                MemoryClient,
                MemoryConfig,
                MemorySettings,
                Neo4jConfig,
            )
            from pydantic import SecretStr

            from retail_agent.integrations.databricks.embeddings import DatabricksEmbedder

            mlflow.langchain.autolog()

            # Create persistent event loop before anything async
            self._loop = _create_background_loop()

            # Create Databricks embedder for semantic memory search.
            # Uses mlflow.deployments which handles auth automatically
            # inside the Model Serving container.
            embedding_model = os.environ.get(
                "RETAIL_AGENT_EMBEDDING_MODEL", "databricks-bge-large-en"
            )
            embedding_dims = int(
                os.environ.get("RETAIL_AGENT_EMBEDDING_DIMENSIONS", "1024")
            )

            settings = MemorySettings(
                neo4j=Neo4jConfig(
                    uri=os.environ["NEO4J_URI"],
                    password=SecretStr(os.environ["NEO4J_PASSWORD"]),
                ),
                embedding=EmbeddingConfig(
                    dimensions=embedding_dims,
                ),
                llm=None,
                extraction=ExtractionConfig(extractor_type=ExtractorType.NONE),
                memory=MemoryConfig(multi_tenant=True),
            )
            embedder = DatabricksEmbedder(
                model=embedding_model,
                dims=embedding_dims,
            )
            if not embedder.validate_endpoint():
                embedder = None
            self._embedder = embedder

            self._client = MemoryClient(settings, embedder=embedder)

            # Connect MemoryClient on the persistent loop so the Neo4j
            # driver is bound to it from the start
            future = asyncio.run_coroutine_threadsafe(
                self._client.connect(), self._loop
            )
            future.result(timeout=30)

            from retail_agent.agent.graph import create_agent
            self._agent = create_agent()
            self._initialized = True
            self._init_error = None

        except Exception as e:
            self._init_error = f"Failed to initialize agent: {e}\n{traceback.format_exc()}"
            self._agent = None

    def predict(self, messages, context=None, custom_inputs=None):
        """Sync entry point required by Databricks Model Serving.

        Dispatches async work to the persistent background event loop
        via run_coroutine_threadsafe(). This ensures the Neo4j async
        driver always runs on the same loop it was connected on.
        """
        self._ensure_initialized()

        # Not yet initialized. Allow this only during MLflow logging or
        # validation, when Databricks endpoint secrets are not available.
        if self._agent is None:
            if self._init_error:
                raise RuntimeError(self._init_error)
            if not _allow_uninitialized_for_logging():
                raise RuntimeError(
                    "Agent is not initialized. NEO4J_URI and NEO4J_PASSWORD "
                    "must be supplied through Databricks serving environment "
                    "variables."
                )
            return ChatAgentResponse(
                messages=[ChatAgentMessage(
                    role="assistant",
                    content=(
                        "Model loaded successfully. Runtime dependencies are "
                        "deferred until Databricks serving secrets are available."
                    ),
                    id=str(uuid4()),
                )]
            )

        future = asyncio.run_coroutine_threadsafe(
            self._async_predict(messages, context, custom_inputs),
            self._loop,
        )
        return future.result(timeout=120)

    async def _async_predict(self, messages, context, custom_inputs):
        """Async implementation — invokes agent with RetailContext."""
        # Extract session_id and user_id from custom_inputs
        session_id = None
        user_id = None
        demo_mode_hint = None
        if custom_inputs and isinstance(custom_inputs, dict):
            session_id = custom_inputs.get("session_id")
            user_id = custom_inputs.get("user_id")
            demo_mode_hint = get_demo_mode_hint(custom_inputs.get("demo_mode"))
        if not session_id:
            session_id = f"serving-{uuid4()}"

        # Build context for this request
        from retail_agent.agent.context import RetailContext
        retail_context = RetailContext(
            client=self._client,
            embedder=self._embedder,
            session_id=session_id,
            user_id=user_id,
        )
        if user_id:
            await self._client.users.upsert_user(identifier=user_id)

        request_messages = [{"role": m.role, "content": m.content} for m in messages]
        if demo_mode_hint:
            request_messages.insert(0, {"role": "system", "content": demo_mode_hint})
        request = {"messages": request_messages}
        _update_current_trace(
            session_id=session_id,
            user_id=user_id,
            demo_mode=custom_inputs.get("demo_mode") if custom_inputs else None,
        )

        timing_callback = ToolTimingCallback()
        result = await self._agent.ainvoke(
            request,
            config={"callbacks": [timing_callback]},
            context=retail_context,
        )
        demo_trace = extract_demo_trace(
            result.get("messages", []),
            tool_timings=timing_callback.completed,
        )
        trace_id = _current_or_last_trace_id()
        if trace_id:
            demo_trace["mlflow_trace_id"] = trace_id

        # Extract the final AI message from LangGraph output
        ai_messages = [
            ChatAgentMessage(role="assistant", content=msg.content, id=str(uuid4()))
            for msg in result["messages"]
            if hasattr(msg, "type") and msg.type == "ai" and msg.content
        ]

        if not ai_messages:
            ai_messages = [ChatAgentMessage(role="assistant", content="No response generated.", id=str(uuid4()))]

        return ChatAgentResponse(
            messages=ai_messages,
            custom_outputs={"demo_trace": demo_trace},
        )


AGENT = RetailAgent()
mlflow.models.set_model(AGENT)


def _update_current_trace(
    *,
    session_id: str,
    user_id: str | None,
    demo_mode: object,
) -> None:
    try:
        tags = {"retail_agent.session_id": session_id}
        if isinstance(demo_mode, str) and demo_mode:
            tags["retail_agent.demo_mode"] = demo_mode
        mlflow.update_current_trace(
            session_id=session_id,
            user=user_id,
            tags=tags,
        )
    except Exception:
        return


def _current_or_last_trace_id() -> str | None:
    try:
        trace_id = mlflow.get_active_trace_id() or mlflow.get_last_active_trace_id()
    except Exception:
        return None
    return trace_id if isinstance(trace_id, str) and trace_id else None
