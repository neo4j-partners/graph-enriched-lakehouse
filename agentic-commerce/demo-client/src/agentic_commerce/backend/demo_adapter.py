from __future__ import annotations

from typing import Any, cast

from .models import (
    CitedSource,
    DemoWarning,
    DiagnosisPathStep,
    GraphHop,
    KnowledgeChunk,
    MemoryWrite,
    ProductCard,
    ProfileChip,
    RecommendedAction,
    ToolTimelineItem,
)


def extract_answer(raw_response: dict[str, Any]) -> str:
    messages = raw_response.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            message_data = cast(dict[str, Any], message)
            if (
                message_data.get("role") == "assistant"
                and message_data.get("content")
            ):
                return str(message_data["content"])
    return "No response generated."


def extract_demo_trace(raw_response: dict[str, Any]) -> dict[str, Any] | None:
    custom_outputs = raw_response.get("custom_outputs")
    if not isinstance(custom_outputs, dict):
        return None

    demo_trace = custom_outputs.get("demo_trace")
    if isinstance(demo_trace, dict):
        return demo_trace
    return None


def adapt_search_trace(
    raw_response: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(raw_response)
    trace = extract_demo_trace(raw_response)
    warnings: list[DemoWarning] = []

    if trace is None:
        return {
            "answer": answer,
            "trace_source": "unavailable",
            "summary": answer,
            "warnings": [
                DemoWarning(
                    code="trace_unavailable",
                    message="The live endpoint returned prose without demo trace metadata.",
                )
            ],
        }

    warnings.extend(_warnings(trace.get("warnings")))
    product_results = _dedupe_products(_products(trace.get("product_results")))
    related_products = _dedupe_products(
        _products(trace.get("related_products")),
        exclude={_product_identity(product) for product in product_results},
    )
    knowledge_chunks = _knowledge_chunks(trace.get("knowledge_chunks"))
    return {
        "answer": answer,
        "trace_source": _trace_source(trace, product_results or knowledge_chunks),
        "summary": _search_summary(trace, answer, product_results, knowledge_chunks),
        "product_picks": product_results,
        "related_products": related_products,
        "profile_chips": _profile_chips(trace.get("profile")),
        "memory_writes": _memory_writes(trace.get("memory_writes")),
        "tool_timeline": _tool_timeline(trace.get("tool_timeline")),
        "graph_hops": _graph_hops(trace.get("graph_hops"), knowledge_chunks),
        "knowledge_chunks": knowledge_chunks,
        "warnings": warnings,
    }


def adapt_diagnosis_trace(
    raw_response: dict[str, Any],
) -> dict[str, Any]:
    answer = extract_answer(raw_response)
    trace = extract_demo_trace(raw_response)

    if trace is None:
        return {
            "answer": answer,
            "trace_source": "unavailable",
            "summary": answer,
            "warnings": [
                DemoWarning(
                    code="trace_unavailable",
                    message="The live endpoint returned prose without demo trace metadata.",
                )
            ],
        }

    knowledge_chunks = _knowledge_chunks(trace.get("knowledge_chunks"))
    diagnosis = trace.get("diagnosis")
    diagnosis_data = diagnosis if isinstance(diagnosis, dict) else {}
    warnings = _warnings(trace.get("warnings"))

    actions = _recommended_actions(
        diagnosis_data.get("recommended_actions")
        or diagnosis_data.get("actions")
        or trace.get("recommended_actions")
    )
    if not actions:
        actions = _solutions_to_actions(knowledge_chunks)

    path = _diagnosis_path(diagnosis_data, knowledge_chunks)
    sources = _sources(trace.get("sources"), knowledge_chunks)

    return {
        "answer": answer,
        "trace_source": _trace_source(trace, knowledge_chunks or path),
        "summary": _diagnosis_summary(
            diagnosis_data,
            trace,
            answer,
            actions,
            knowledge_chunks,
        ),
        "confidence": _float_or_none(diagnosis_data.get("confidence")),
        "path": path,
        "recommended_actions": actions,
        "compatible_alternatives": _products(
            diagnosis_data.get("compatible_alternatives")
            or trace.get("compatible_alternatives")
            or trace.get("related_products")
        ),
        "cited_sources": sources,
        "tool_timeline": _tool_timeline(trace.get("tool_timeline")),
        "knowledge_chunks": knowledge_chunks,
        "warnings": warnings,
    }


def _trace_source(trace: dict[str, Any], has_live_data: Any) -> str:
    source = trace.get("trace_source")
    if source in {"live", "sample", "inferred", "unavailable"}:
        return str(source)
    return "live" if has_live_data else "unavailable"


def _products(value: Any) -> list[ProductCard]:
    rows = _list(value)
    products: list[ProductCard] = []
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("product_name")
        if not name:
            continue
        products.append(
            ProductCard(
                id=_string_or_none(item.get("id") or item.get("product_id")),
                name=str(name),
                brand=_string_or_none(item.get("brand")),
                category=_string_or_none(item.get("category")),
                description=_string_or_none(item.get("description")),
                price=_float_or_none(item.get("price")),
                in_stock=_bool_or_none(item.get("in_stock")),
                image_url=_string_or_none(item.get("image_url")),
                score=_float_or_none(
                    item.get("score") or item.get("relevance") or item.get("rank_score")
                ),
                rationale=_string_or_none(
                    item.get("rationale")
                    or item.get("supporting_context")
                    or item.get("description")
                ),
                signals=_strings(
                    item.get("signals") or item.get("features") or [f"Rank {index}"]
                ),
            )
        )
    return products


def _dedupe_products(
    products: list[ProductCard],
    *,
    exclude: set[str] | None = None,
) -> list[ProductCard]:
    seen = set(exclude or set())
    deduped: list[ProductCard] = []
    for product in products:
        key = _product_identity(product)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(product)
    return deduped


def _product_identity(product: ProductCard) -> str:
    return (
        product.id
        or f"{product.brand or ''}:{product.name}:{product.category or ''}"
    ).strip().lower()


def _search_summary(
    trace: dict[str, Any],
    answer: str,
    product_results: list[ProductCard],
    knowledge_chunks: list[KnowledgeChunk],
) -> str:
    explicit = _string_or_none(trace.get("summary"))
    if explicit:
        return explicit

    if product_results:
        names = [product.name for product in product_results[:3]]
        name_list = _human_list(names)
        suffix = (
            f" I also found {len(knowledge_chunks)} relevant knowledge source"
            f"{'' if len(knowledge_chunks) == 1 else 's'}."
            if knowledge_chunks
            else ""
        )
        return (
            f"Found {len(product_results)} live product pick"
            f"{'' if len(product_results) == 1 else 's'}"
            f"{f': {name_list}' if name_list else ''}.{suffix}"
        )

    return answer


def _diagnosis_summary(
    diagnosis_data: dict[str, Any],
    trace: dict[str, Any],
    answer: str,
    actions: list[RecommendedAction],
    knowledge_chunks: list[KnowledgeChunk],
) -> str:
    explicit = (
        _string_or_none(diagnosis_data.get("summary"))
        or _string_or_none(trace.get("summary"))
    )
    if explicit:
        return explicit

    if actions or knowledge_chunks:
        parts: list[str] = []
        if knowledge_chunks:
            parts.append(
                f"Found {len(knowledge_chunks)} relevant diagnosis source"
                f"{'' if len(knowledge_chunks) == 1 else 's'}"
            )
        if actions:
            action_labels = [action.label for action in actions[:3]]
            parts.append(f"recommended actions: {_human_list(action_labels)}")
        return f"{'; '.join(parts)}."

    return answer


def _human_list(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _knowledge_chunks(value: Any) -> list[KnowledgeChunk]:
    rows = _list(value)
    chunks: list[KnowledgeChunk] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("context") or item.get("snippet")
        if not text:
            continue
        chunks.append(
            KnowledgeChunk(
                id=_string_or_none(item.get("id") or item.get("chunk_id")),
                title=_string_or_none(item.get("title")),
                text=str(text),
                source_type=_string_or_none(item.get("source_type")),
                score=_float_or_none(item.get("score") or item.get("relevance")),
                features=_strings(item.get("features")),
                symptoms=_strings(item.get("symptoms")),
                solutions=_strings(item.get("solutions")),
                related_products=_strings(
                    item.get("related_products")
                    or item.get("products_with_same_solution")
                ),
            )
        )
    return chunks


def _profile_chips(value: Any) -> list[ProfileChip]:
    rows = _list(value)
    chips: list[ProfileChip] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("category") or item.get("type")
        raw_value = item.get("value") or item.get("preference")
        if not label or raw_value is None:
            continue
        chips.append(
            ProfileChip(
                label=str(label),
                value=str(raw_value),
                kind=_string_or_none(item.get("kind") or item.get("preference_type")),
            )
        )
    return chips


def _memory_writes(value: Any) -> list[MemoryWrite]:
    rows = _list(value)
    writes: list[MemoryWrite] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("preference_type") or item.get("kind")
        raw_value = item.get("value") or item.get("preference_value")
        if not label or raw_value is None:
            continue
        writes.append(
            MemoryWrite(
                label=str(label),
                value=str(raw_value),
                kind=_string_or_none(item.get("kind") or item.get("preference_type")),
                stored=_bool_or_none(item.get("stored")),
            )
        )
    return writes


def _tool_timeline(value: Any) -> list[ToolTimelineItem]:
    rows = _list(value)
    timeline: list[ToolTimelineItem] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool_name") or item.get("name")
        if not tool_name:
            continue
        timeline.append(
            ToolTimelineItem(
                tool_name=str(tool_name),
                status=str(item.get("status") or "completed"),
                label=_string_or_none(item.get("label")),
                duration_ms=_int_or_none(item.get("duration_ms")),
                summary=_string_or_none(item.get("summary")),
            )
        )
    return timeline


def _graph_hops(
    value: Any,
    knowledge_chunks: list[KnowledgeChunk],
) -> list[GraphHop]:
    rows = _list(value)
    hops: list[GraphHop] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        relationship = item.get("relationship")
        target = item.get("target")
        if not source or not relationship or not target:
            continue
        hops.append(
            GraphHop(
                source=str(source),
                relationship=str(relationship),
                target=str(target),
                score=_float_or_none(item.get("score")),
            )
        )
    if hops:
        return hops

    for chunk in knowledge_chunks:
        for symptom in chunk.symptoms:
            for solution in chunk.solutions:
                hops.append(
                    GraphHop(
                        source=symptom,
                        relationship="PROVIDES_SOLUTION",
                        target=solution,
                        score=chunk.score,
                    )
                )
    return hops


def _diagnosis_path(
    diagnosis_data: dict[str, Any],
    knowledge_chunks: list[KnowledgeChunk],
) -> list[DiagnosisPathStep]:
    rows = _list(diagnosis_data.get("path"))
    path: list[DiagnosisPathStep] = []
    for item in rows:
        if isinstance(item, dict) and item.get("label"):
            path.append(
                DiagnosisPathStep(
                    label=str(item["label"]),
                    detail=_string_or_none(item.get("detail")),
                )
            )
    if path:
        return path

    symptoms = _strings(diagnosis_data.get("symptoms"))
    solutions = _strings(diagnosis_data.get("solutions"))
    if not symptoms:
        symptoms = [symptom for chunk in knowledge_chunks for symptom in chunk.symptoms]
    if not solutions:
        solutions = [solution for chunk in knowledge_chunks for solution in chunk.solutions]
    if symptoms:
        path.append(DiagnosisPathStep(label="Symptom", detail=symptoms[0]))
    if solutions:
        path.append(DiagnosisPathStep(label="Solution", detail=solutions[0]))
    return path


def _recommended_actions(value: Any) -> list[RecommendedAction]:
    rows = _list(value)
    actions: list[RecommendedAction] = []
    for item in rows:
        if isinstance(item, str):
            actions.append(RecommendedAction(label=item))
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name") or item.get("action")
            if label:
                actions.append(
                    RecommendedAction(
                        label=str(label),
                        description=_string_or_none(item.get("description")),
                        priority=_string_or_none(item.get("priority")),
                    )
                )
    return actions


def _solutions_to_actions(chunks: list[KnowledgeChunk]) -> list[RecommendedAction]:
    seen: set[str] = set()
    actions: list[RecommendedAction] = []
    for chunk in chunks:
        for solution in chunk.solutions:
            if solution in seen:
                continue
            seen.add(solution)
            actions.append(RecommendedAction(label=solution))
    return actions


def _sources(value: Any, chunks: list[KnowledgeChunk]) -> list[CitedSource]:
    rows = _list(value)
    sources: list[CitedSource] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        sources.append(
            CitedSource(
                id=_string_or_none(item.get("id")),
                title=_string_or_none(item.get("title")),
                source_type=_string_or_none(item.get("source_type")),
                snippet=_string_or_none(item.get("snippet")),
                score=_float_or_none(item.get("score")),
            )
        )
    if sources:
        return sources

    return [
        CitedSource(
            id=chunk.id,
            title=chunk.title,
            source_type=chunk.source_type,
            snippet=chunk.text[:240],
            score=chunk.score,
        )
        for chunk in chunks
    ]


def _warnings(value: Any) -> list[DemoWarning]:
    warnings: list[DemoWarning] = []
    for item in _list(value):
        if isinstance(item, str):
            warnings.append(DemoWarning(code="upstream_warning", message=item))
        elif isinstance(item, dict):
            message = item.get("message")
            if message:
                warnings.append(
                    DemoWarning(
                        code=str(item.get("code") or "upstream_warning"),
                        message=str(message),
                    )
                )
    return warnings


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value) if item is not None]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)
