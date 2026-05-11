"""Diagnostics tool for verifying the deployed agent environment.

Reports library versions, client status, and capability flags so
check_endpoint.py can confirm the correct code is deployed.
"""

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.agent.context import RetailContext


@tool
def agent_diagnostics(
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Return diagnostic information about the agent environment.

    Use this tool when asked about versions, status, or diagnostics.
    """
    info = {}

    # Library version
    try:
        import neo4j_agent_memory

        info["neo4j_agent_memory_version"] = getattr(
            neo4j_agent_memory, "__version__", "unknown"
        )
    except ImportError:
        info["neo4j_agent_memory_version"] = "not installed"

    # Client status
    client = runtime.context.client
    info["client_initialized"] = client is not None
    if client is not None:
        info["has_graph"] = getattr(client, "is_connected", False)
        info["has_embedder"] = runtime.context.embedder is not None
        info["has_short_term"] = getattr(client, "short_term", None) is not None
        info["has_long_term"] = getattr(client, "long_term", None) is not None

    # Session info
    info["session_id"] = runtime.context.session_id

    # Serving module version check
    try:
        import importlib
        import inspect

        serving = importlib.import_module("retail_agent.agent.serving")
        source = inspect.getsource(serving.RetailAgent.predict)
        if "run_coroutine_threadsafe" in source:
            info["async_bridge"] = "persistent_loop"
        elif "asyncio.run" in source:
            info["async_bridge"] = "asyncio_run"
        else:
            info["async_bridge"] = "unknown"
    except Exception:
        info["async_bridge"] = "check_failed"

    # ---- Tool injection instrumentation ----
    try:
        from retail_agent.agent.graph import ALL_TOOLS

        # Per-tool: langchain-core's detected injectable params
        for t in ALL_TOOLS:
            info[f"tool_{t.name}_injected_keys"] = sorted(t._injected_args_keys)
            info[f"tool_{t.name}_schema_fields"] = sorted(
                t.get_input_schema().model_fields.keys()
            )

        # ToolNode-level: langgraph's injection mapping
        from langgraph.prebuilt import ToolNode

        node = ToolNode(ALL_TOOLS)
        for tool_name, injected in node._injected_args.items():
            info[f"tool_{tool_name}_injected"] = {
                "state": injected.state,
                "store": injected.store,
                "runtime": injected.runtime,
            }
    except Exception as exc:
        info["injection_instrumentation_error"] = f"{type(exc).__name__}: {exc}"

    import json

    return json.dumps(info, indent=2)


DIAGNOSTICS_TOOLS = [agent_diagnostics]
