"""Shared context for Agentic Commerce agent tools.

RetailContext for dependency injection via ToolRuntime.
This dataclass is injected into tools via ToolRuntime[RetailContext] at
invocation time. The MemoryClient and session_id are constructed by whoever
invokes the agent — locally or via the Databricks serving adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RetailContext:
    """All external dependencies for Agentic Commerce agent tools.

    Injected by LangGraph at invocation time via ToolRuntime.
    Constructed by the Databricks Model Serving adapter.
    """

    client: Any
    embedder: Any | None = None
    session_id: str | None = None
    user_id: str | None = None

    @property
    def memory_user_identifier(self) -> str | None:
        """Identifier used for neo4j-agent-memory multi-tenant scoping."""
        if self.user_id:
            return self.user_id
        if self.session_id:
            return f"session:{self.session_id}"
        return None
