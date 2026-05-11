"""Reasoning trace tools using neo4j-agent-memory.

Records multi-step agent reasoning and enables learning from past tasks:
- record_reasoning_trace: open a trace, record steps/tool calls, and close it
- recall_past_reasoning: find similar past reasoning traces by semantic search
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

from retail_agent.agent.context import RetailContext

logger = logging.getLogger(__name__)


@tool
async def record_reasoning_trace(
    task: str,
    steps: list[dict],
    outcome: str,
    success: bool,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Record a completed reasoning trace for a multi-step task.

    Use this tool after completing a multi-step task such as product
    comparison, troubleshooting workflow, or purchase recommendation.
    Recording traces lets the agent learn from past approaches and
    improve over time.

    Args:
        task: Description of the task (e.g. 'troubleshoot flat running shoes').
        steps: List of step dicts, each with 'thought' (reasoning),
            'action' (tool or action taken), and optional 'observation' (result).
        outcome: Final outcome or answer.
        success: Whether the task was completed successfully.
    """
    client = runtime.context.client
    session_id = runtime.context.session_id or "default"
    user_identifier = runtime.context.memory_user_identifier

    try:
        # Start the trace
        trace = await client.reasoning.start_trace(
            session_id=session_id,
            task=task,
            generate_embedding=True,
            user_identifier=user_identifier,
        )

        # Record each step with its tool calls
        for step_data in steps:
            step = await client.reasoning.add_step(
                trace.id,
                thought=step_data.get("thought"),
                action=step_data.get("action"),
                observation=step_data.get("observation"),
                generate_embedding=True,
            )

            # If the step includes tool call info, record it
            if "tool_name" in step_data:
                await client.reasoning.record_tool_call(
                    step.id,
                    tool_name=step_data["tool_name"],
                    arguments=step_data.get("arguments", {}),
                    result=step_data.get("result"),
                    status="success" if step_data.get("tool_success", True) else "failure",
                    duration_ms=step_data.get("duration_ms"),
                )

        # Complete the trace
        await client.reasoning.complete_trace(
            trace.id,
            outcome=outcome,
            success=success,
        )

        return json.dumps({
            "recorded": True,
            "trace_id": str(trace.id),
            "task": task,
            "step_count": len(steps),
            "success": success,
        })
    except Exception as e:
        logger.warning("Failed to record reasoning trace: %s", e)
        return json.dumps({"error": "Failed to record trace", "detail": str(e)})


@tool
async def recall_past_reasoning(
    task_description: str,
    limit: int = 3,
    *,
    runtime: ToolRuntime[RetailContext],
) -> str:
    """Find past reasoning traces for tasks similar to the current one.

    Use this tool when starting a task that may have been attempted before.
    Returns successful past approaches including the steps taken, tools used,
    and outcomes achieved. Helps the agent learn from experience rather than
    starting from scratch.

    Args:
        task_description: Description of the current task to find similar
            past traces for (e.g. 'compare trail shoes under $200').
        limit: Maximum number of past traces to return.
    """
    client = runtime.context.client
    embedder = runtime.context.embedder
    user_identifier = runtime.context.memory_user_identifier

    try:
        if embedder is None:
            return json.dumps({
                "query": task_description,
                "past_traces": [],
                "count": 0,
                "note": "No embedder is configured for reasoning recall.",
            })
        if not user_identifier:
            return json.dumps({
                "query": task_description,
                "past_traces": [],
                "count": 0,
                "note": "No user identifier is available for scoped reasoning recall.",
            })

        task_embedding = await embedder.embed(task_description)
        rows = await client.graph.execute_read(
            """
            CALL db.index.vector.queryNodes('task_embedding_idx', $candidate_limit, $embedding)
            YIELD node, score
            WHERE score >= $threshold AND node.success = true
            WITH node, score
            MATCH (:User {identifier: $user_identifier})-[:HAS_TRACE]->(node)
            RETURN node.id AS trace_id, score
            ORDER BY score DESC
            LIMIT $limit
            """,
            {
                "embedding": task_embedding,
                "candidate_limit": max(limit * 5, limit),
                "threshold": 0.5,
                "limit": limit,
                "user_identifier": user_identifier,
            },
        )

        results = []
        for row in rows:
            # Get full trace with steps
            full_trace = await client.reasoning.get_trace(row["trace_id"])
            if not full_trace:
                continue

            trace_info = {
                "task": full_trace.task,
                "outcome": full_trace.outcome,
                "success": full_trace.success,
                "similarity": row["score"],
                "steps": [],
            }

            if full_trace.steps:
                for step in full_trace.steps:
                    step_info = {
                        "thought": step.thought,
                        "action": step.action,
                        "observation": step.observation,
                    }
                    trace_info["steps"].append(step_info)

            results.append(trace_info)

        return json.dumps({
            "query": task_description,
            "past_traces": results,
            "count": len(results),
        })
    except Exception as e:
        logger.warning("Failed to recall past reasoning: %s", e)
        return json.dumps({"error": "Failed to search past traces", "detail": str(e)})


# Flat tool list for import by retail_agent.agent.graph
REASONING_TOOLS = [record_reasoning_trace, recall_past_reasoning]
