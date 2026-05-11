"""Extract demo metadata from LangGraph tool calls and results."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


TOOL_OUTPUT_FIELDS = {
    "search_products": "product_results",
    "get_related_products": "related_products",
    "knowledge_search": "knowledge_chunks",
    "hybrid_knowledge_search": "knowledge_chunks",
    "diagnose_product_issue": "diagnosis",
    "get_user_profile": "profile",
    "track_preference": "memory_writes",
    "recommend_for_user": "product_results",
}

DEMO_MODE_HINTS = {
    "agentic_search": (
        "Demo mode: agentic_search. Prefer product discovery tools for "
        "shopping and recommendation requests. Use search_products for "
        "catalog matches, get_related_products for graph-backed adjacent "
        "recommendations, and get_user_profile or track_preference when "
        "user-specific context is available. Demo catalog examples include "
        "trail running shoes, rain shells, outdoor gear, and fitness apparel. "
        "Return normal assistant prose."
    ),
    "issue_diagnosis": (
        "Demo mode: issue_diagnosis. Prefer support and knowledge-graph "
        "tools for troubleshooting requests. Use knowledge_search or "
        "hybrid_knowledge_search for symptoms, sources, features, and "
        "solutions. Use diagnose_product_issue when a specific product can "
        "be identified. Demo troubleshooting examples include flat running "
        "shoe midsoles, outsole peeling, fit issues, and gear durability. "
        "Return normal assistant prose."
    ),
}

def get_demo_mode_hint(demo_mode: Any) -> str | None:
    """Return a prompt hint for supported demo modes."""
    if not isinstance(demo_mode, str):
        return None
    return DEMO_MODE_HINTS.get(demo_mode)


def extract_demo_trace(
    messages: Sequence[Any],
    tool_timings: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract structured demo trace data from LangGraph messages.

    The extractor only uses real AI tool calls and ToolMessage outputs from the
    completed LangGraph run. Malformed outputs are recorded as warnings and do
    not fail the request.
    """
    trace = _empty_trace()
    tool_names_by_id: dict[str, str] = {}
    timings_by_id, timings_by_name = _index_tool_timings(tool_timings)
    saw_tool_event = False

    for message in messages:
        message_type = getattr(message, "type", None)

        if message_type == "ai":
            tool_calls = _get_tool_calls(message)
            for call in tool_calls:
                saw_tool_event = True
                tool_name = _string_value(call.get("name"))
                tool_call_id = _string_value(call.get("id"))
                if tool_call_id and tool_name:
                    tool_names_by_id[tool_call_id] = tool_name
                trace["tool_timeline"].append(_tool_call_entry(call))

        if message_type == "tool":
            saw_tool_event = True
            tool_call_id = _string_value(getattr(message, "tool_call_id", None))
            tool_name = _string_value(getattr(message, "name", None))
            if not tool_name and tool_call_id:
                tool_name = tool_names_by_id.get(tool_call_id)
            content = getattr(message, "content", "")
            _capture_tool_result(
                trace,
                tool_name,
                tool_call_id,
                content,
                message,
                timings_by_id,
                timings_by_name,
            )

    if saw_tool_event:
        trace["trace_source"] = "live"
    else:
        trace["trace_source"] = "unavailable"
        trace["warnings"].append(
            "No LangGraph tool calls or tool results were captured."
        )

    return trace


def _empty_trace() -> dict[str, Any]:
    return {
        "trace_source": "unavailable",
        "tool_timeline": [],
        "product_results": [],
        "related_products": [],
        "knowledge_chunks": [],
        "diagnosis": None,
        "profile": [],
        "memory_writes": [],
        "warnings": [],
    }


def _get_tool_calls(message: Any) -> list[dict[str, Any]]:
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return []
    return [dict(call) for call in tool_calls if isinstance(call, Mapping)]


def _tool_call_entry(call: Mapping[str, Any]) -> dict[str, Any]:
    args = call.get("args")
    return {
        "event": "tool_call",
        "tool_name": _string_value(call.get("name")),
        "tool_call_id": _string_value(call.get("id")),
        "input_keys": sorted(args.keys()) if isinstance(args, Mapping) else [],
    }


def _capture_tool_result(
    trace: dict[str, Any],
    tool_name: str | None,
    tool_call_id: str | None,
    content: Any,
    message: Any,
    timings_by_id: dict[str, dict[str, Any]],
    timings_by_name: dict[str, list[dict[str, Any]]],
) -> None:
    content_text = _content_to_text(content)
    entry = {
        "event": "tool_result",
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "status": _string_value(getattr(message, "status", None)),
        "content_type": "json",
    }
    _apply_tool_timing(entry, tool_name, tool_call_id, timings_by_id, timings_by_name)

    payload = _parse_json(content_text)
    if payload is None:
        entry["content_type"] = "text"
        entry["output_preview"] = _preview(content_text)
        trace["tool_timeline"].append(entry)
        trace["warnings"].append(
            _tool_warning(tool_name, "returned non-JSON output.")
        )
        return

    entry["json_keys"] = sorted(payload.keys()) if isinstance(payload, Mapping) else []
    entry["summary"] = _json_summary(payload)
    trace["tool_timeline"].append(entry)
    _normalize_tool_payload(trace, tool_name, payload)


def _index_tool_timings(
    tool_timings: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    timings_by_id: dict[str, dict[str, Any]] = {}
    timings_by_name: dict[str, list[dict[str, Any]]] = {}
    if not tool_timings:
        return timings_by_id, timings_by_name

    for raw_timing in tool_timings:
        timing = dict(raw_timing)
        tool_call_id = _string_value(timing.get("tool_call_id"))
        tool_name = _string_value(timing.get("tool_name"))
        if tool_call_id:
            timings_by_id[tool_call_id] = timing
        if tool_name:
            timings_by_name.setdefault(tool_name, []).append(timing)
    return timings_by_id, timings_by_name


def _apply_tool_timing(
    entry: dict[str, Any],
    tool_name: str | None,
    tool_call_id: str | None,
    timings_by_id: dict[str, dict[str, Any]],
    timings_by_name: dict[str, list[dict[str, Any]]],
) -> None:
    timing = timings_by_id.get(tool_call_id or "")
    if timing is None and tool_name:
        candidates = timings_by_name.get(tool_name)
        if candidates:
            timing = candidates.pop(0)

    if timing is None:
        return

    duration_ms = _int_value(timing.get("duration_ms"))
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms


def _normalize_tool_payload(
    trace: dict[str, Any],
    tool_name: str | None,
    payload: Any,
) -> None:
    if not tool_name:
        trace["warnings"].append("A tool result did not include a tool name.")
        return

    if tool_name not in TOOL_OUTPUT_FIELDS:
        return

    if not isinstance(payload, Mapping):
        trace["warnings"].append(
            _tool_warning(tool_name, "returned JSON that is not an object.")
        )
        return

    if "error" in payload:
        trace["warnings"].append(_tool_warning(tool_name, str(payload["error"])))

    if tool_name == "search_products":
        trace["product_results"].extend(_normalize_rows(payload.get("products")))
    elif tool_name == "get_related_products":
        source_product_id = _string_value(payload.get("source_product_id"))
        related_rows = _normalize_rows(payload.get("related_products"))
        for row in related_rows:
            if source_product_id and "source_product_id" not in row:
                row["source_product_id"] = source_product_id
        trace["related_products"].extend(related_rows)
    elif tool_name in {"knowledge_search", "hybrid_knowledge_search"}:
        trace["knowledge_chunks"].extend(
            _normalize_knowledge_chunks(payload.get("results"))
        )
    elif tool_name == "diagnose_product_issue":
        trace["diagnosis"] = _normalize_diagnosis(payload)
        trace["knowledge_chunks"].extend(
            _normalize_knowledge_chunks(payload.get("source_documents"))
        )
    elif tool_name == "get_user_profile":
        trace["profile"].extend(_normalize_rows(payload.get("preferences")))
    elif tool_name == "track_preference":
        trace["memory_writes"].append(_json_safe(payload))
    elif tool_name == "recommend_for_user":
        trace["product_results"].extend(
            _normalize_rows(payload.get("recommendations"))
        )
        preferences = _string_list(payload.get("preferences_used"))
        trace["profile"].extend(
            {"label": "preference", "value": preference}
            for preference in preferences
        )
        if payload.get("note"):
            trace["warnings"].append(_tool_warning(tool_name, str(payload["note"])))


def _normalize_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if isinstance(item, Mapping):
            rows.append(_json_safe(dict(item)))
    return rows


def _normalize_knowledge_chunks(value: Any) -> list[dict[str, Any]]:
    chunks = []
    for row in _normalize_rows(value):
        chunk = {
            "chunk_id": row.get("chunk_id"),
            "text": row.get("text") or row.get("context"),
            "source_type": row.get("source_type"),
            "score": row.get("score") if "score" in row else row.get("relevance"),
            "features": _string_list(row.get("features")),
            "symptoms": _string_list(row.get("symptoms")),
            "solutions": _string_list(row.get("solutions")),
        }
        related = _string_list(row.get("related_products"))
        same_solution = _string_list(row.get("products_with_same_solution"))
        if related:
            chunk["related_products"] = related
        if same_solution:
            chunk["products_with_same_solution"] = same_solution
        chunks.append(
            {key: value for key, value in chunk.items() if value not in (None, [])}
        )
    return chunks


def _normalize_diagnosis(payload: Mapping[str, Any]) -> dict[str, Any]:
    diagnosis_rows = _normalize_rows(payload.get("diagnosis"))
    diagnosis = {
        "product_id": payload.get("product_id"),
        "items": diagnosis_rows,
        "symptoms": _unique_strings(
            symptom
            for row in diagnosis_rows
            for symptom in _string_list(row.get("symptoms"))
        ),
        "solutions": _unique_strings(
            solution
            for row in diagnosis_rows
            for solution in _string_list(row.get("solutions"))
        ),
        "features": _unique_strings(
            feature
            for row in diagnosis_rows
            for feature in _string_list(row.get("features"))
        ),
    }
    product_names = _unique_strings(
        row.get("product_name") for row in diagnosis_rows if row.get("product_name")
    )
    if product_names:
        diagnosis["product_name"] = product_names[0]
    if "error" in payload:
        diagnosis["error"] = payload["error"]
    return _json_safe(
        {key: value for key, value in diagnosis.items() if value not in (None, [])}
    )


def _parse_json(content: str) -> Any | None:
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content)
    except TypeError:
        return str(content)


def _json_summary(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        summary = {}
        for key, value in payload.items():
            if isinstance(value, list):
                summary[key] = len(value)
            elif isinstance(value, Mapping):
                summary[key] = sorted(value.keys())
            else:
                summary[key] = type(value).__name__
        return summary
    if isinstance(payload, list):
        return {"items": len(payload)}
    return {"type": type(payload).__name__}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
            if _is_safe_key(str(key))
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_safe_key(key: str) -> bool:
    lowered = key.lower()
    unsafe_parts = (
        "authorization",
        "token",
        "secret",
        "password",
        "credential",
        "header",
    )
    return not any(part in lowered for part in unsafe_parts)


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _unique_strings(values: Any) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        if isinstance(value, str) and value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _preview(content: str, limit: int = 500) -> str:
    clean = " ".join(content.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit - 3]}..."


def _tool_warning(tool_name: str | None, message: str) -> str:
    if tool_name:
        return f"{tool_name} {message}"
    return f"Unknown tool {message}"
