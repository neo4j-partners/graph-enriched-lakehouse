import re
import time
from dataclasses import dataclass
from typing import Any, NoReturn
from uuid import uuid4

from databricks.sdk.service.iam import User as UserOut

from .core import Dependencies, create_router
from .core._config import AppConfig, logger
from .demo_adapter import adapt_diagnosis_trace, adapt_search_trace
from .models import (
    AgenticSearchIn,
    AgenticSearchOut,
    DemoError,
    IssueDiagnosisIn,
    IssueDiagnosisOut,
    TimingMetadata,
    VersionOut,
)
from .sample_data import diagnosis_sample, search_sample
from .serving_client import ServingInvocationError, invoke_retail_agent

router = create_router()
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    502: {"model": DemoError},
    503: {"model": DemoError},
    504: {"model": DemoError},
}


@dataclass(frozen=True)
class DiagnosisPromptContext:
    product_id: str
    product_name: str


DIAGNOSIS_PRESET_CONTEXTS: dict[str, DiagnosisPromptContext] = {
    "running-shoes-feel-flat": DiagnosisPromptContext(
        product_id="nike-pegasus-40",
        product_name="Nike Pegasus 40",
    ),
    "outsole-peeling": DiagnosisPromptContext(
        product_id="adidas-ultraboost-24",
        product_name="Adidas Ultraboost 24",
    ),
    "tent-condensation": DiagnosisPromptContext(
        product_id="rei-half-dome-tent",
        product_name="REI Half Dome Tent",
    ),
    "sleeping-pad-deflated": DiagnosisPromptContext(
        product_id="therm-a-rest-sleeping-pad",
        product_name="Therm-a-Rest NeoAir XTherm Sleeping Pad",
    ),
    "gel-nimbus-lump": DiagnosisPromptContext(
        product_id="asics-gel-nimbus-26",
        product_name="ASICS Gel-Nimbus 26",
    ),
}


class DemoRouteError(Exception):
    def __init__(self, status_code: int, error: DemoError) -> None:
        self.status_code = status_code
        self.error = error


@router.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    return VersionOut.from_metadata()


@router.get("/current-user", response_model=UserOut, operation_id="currentUser")
def me(user_ws: Dependencies.UserClient):
    return user_ws.current_user.me()


@router.post(
    "/demo/search",
    response_model=AgenticSearchOut,
    operation_id="runAgenticSearch",
    responses=ERROR_RESPONSES,
)
def agentic_search(
    request: AgenticSearchIn,
    config: Dependencies.Config,
    ws: Dependencies.Client,
) -> AgenticSearchOut:
    request_id = str(uuid4())
    session_id = request.session_id or str(uuid4())
    user_id = _effective_user_id(request.user_id, session_id)
    demo_mode = "agentic_search"

    if _use_sample(config.demo_data_mode):
        return search_sample(
            preset_id=request.demo_preset_id,
            prompt=request.prompt,
            request_id=request_id,
            session_id=session_id,
        )

    started = time.perf_counter()
    try:
        result = invoke_retail_agent(
            ws=ws,
            config=config,
            prompt=request.prompt,
            session_id=session_id,
            user_id=user_id,
            demo_mode=demo_mode,
        )
        adapted = adapt_search_trace(result.payload)
        response = AgenticSearchOut(
            source_type="live",
            request_id=request_id,
            session_id=session_id,
            databricks_request_id=result.databricks_request_id,
            timing=TimingMetadata(
                total_ms=int((time.perf_counter() - started) * 1000),
                upstream_ms=result.latency_ms,
            ),
            raw_endpoint_metadata=(
                result.payload if config.demo_include_raw_endpoint_metadata else None
            ),
            **adapted,
        )
        _log_demo_result(
            mode="agentic_search",
            config=config,
            request_id=request_id,
            session_id=session_id,
            source_type=response.source_type,
            latency_ms=response.timing.total_ms,
            databricks_request_id=result.databricks_request_id,
        )
        return response
    except ServingInvocationError as exc:
        return _handle_search_failure(
            exc=exc,
            request=request,
            config=config,
            request_id=request_id,
            session_id=session_id,
            started=started,
        )


@router.post(
    "/demo/diagnose",
    response_model=IssueDiagnosisOut,
    operation_id="runIssueDiagnosis",
    responses=ERROR_RESPONSES,
)
def issue_diagnosis(
    request: IssueDiagnosisIn,
    config: Dependencies.Config,
    ws: Dependencies.Client,
) -> IssueDiagnosisOut:
    request_id = str(uuid4())
    session_id = request.session_id or str(uuid4())
    user_id = _effective_user_id(request.user_id, session_id)
    demo_mode = "issue_diagnosis"

    if _use_sample(config.demo_data_mode):
        return diagnosis_sample(
            preset_id=request.demo_preset_id,
            prompt=request.prompt,
            request_id=request_id,
            session_id=session_id,
        )

    started = time.perf_counter()
    try:
        result = invoke_retail_agent(
            ws=ws,
            config=config,
            prompt=_issue_diagnosis_prompt(request),
            session_id=session_id,
            user_id=user_id,
            demo_mode=demo_mode,
        )
        adapted = adapt_diagnosis_trace(result.payload)
        response = IssueDiagnosisOut(
            source_type="live",
            request_id=request_id,
            session_id=session_id,
            databricks_request_id=result.databricks_request_id,
            timing=TimingMetadata(
                total_ms=int((time.perf_counter() - started) * 1000),
                upstream_ms=result.latency_ms,
            ),
            raw_endpoint_metadata=(
                result.payload if config.demo_include_raw_endpoint_metadata else None
            ),
            **adapted,
        )
        _log_demo_result(
            mode="issue_diagnosis",
            config=config,
            request_id=request_id,
            session_id=session_id,
            source_type=response.source_type,
            latency_ms=response.timing.total_ms,
            databricks_request_id=result.databricks_request_id,
        )
        return response
    except ServingInvocationError as exc:
        return _handle_diagnosis_failure(
            exc=exc,
            request=request,
            config=config,
            request_id=request_id,
            session_id=session_id,
            started=started,
        )


def _use_sample(data_mode: str) -> bool:
    return data_mode.strip().lower() in {"sample", "samples", "mock"}


def _effective_user_id(user_id: str | None, session_id: str) -> str:
    value = user_id.strip() if user_id else ""
    return value or f"session:{session_id}"


def _issue_diagnosis_prompt(request: IssueDiagnosisIn) -> str:
    prompt = request.prompt.strip()
    context = DIAGNOSIS_PRESET_CONTEXTS.get(request.demo_preset_id or "")
    instructions = [
        "Issue diagnosis request.",
        "Use knowledge_search or hybrid_knowledge_search for support context.",
        (
            "Do not call diagnose_product_issue with a guessed product_id. "
            "Only call it when an exact product_id is provided below or clearly "
            "present in the customer issue."
        ),
    ]

    if context is not None:
        instructions.append(
            "Known product context: "
            f"product_id={context.product_id}; product_name={context.product_name}."
        )
        instructions.append(
            "When using diagnose_product_issue, pass exactly that product_id."
        )

    instructions.append(f"Customer issue: {prompt}")
    return "\n".join(instructions)


def _handle_search_failure(
    *,
    exc: ServingInvocationError,
    request: AgenticSearchIn,
    config: AppConfig,
    request_id: str,
    session_id: str,
    started: float,
) -> AgenticSearchOut:
    latency_ms = int((time.perf_counter() - started) * 1000)
    if config.demo_allow_sample_fallback:
        response = search_sample(
            preset_id=request.demo_preset_id,
            prompt=request.prompt,
            request_id=request_id,
            session_id=session_id,
            source_type="fallback",
            warning="Live endpoint unavailable, using sample demo data.",
        )
        response.timing = TimingMetadata(total_ms=latency_ms)
        _log_demo_result(
            mode="agentic_search",
            config=config,
            request_id=request_id,
            session_id=session_id,
            source_type="fallback",
            latency_ms=latency_ms,
            fallback_reason=_fallback_reason(exc),
        )
        return response
    _log_demo_failure(
        mode="agentic_search",
        config=config,
        request_id=request_id,
        session_id=session_id,
        status_code=_safe_error_status(exc),
        latency_ms=latency_ms,
        retryable=exc.retryable,
        fallback_available=config.demo_allow_sample_fallback,
        technical_detail=_technical_detail(exc),
    )
    _raise_demo_error(
        exc,
        fallback_available=config.demo_allow_sample_fallback,
    )


def _handle_diagnosis_failure(
    *,
    exc: ServingInvocationError,
    request: IssueDiagnosisIn,
    config: AppConfig,
    request_id: str,
    session_id: str,
    started: float,
) -> IssueDiagnosisOut:
    latency_ms = int((time.perf_counter() - started) * 1000)
    if config.demo_allow_sample_fallback:
        response = diagnosis_sample(
            preset_id=request.demo_preset_id,
            prompt=request.prompt,
            request_id=request_id,
            session_id=session_id,
            source_type="fallback",
            warning="Live endpoint unavailable, using sample demo data.",
        )
        response.timing = TimingMetadata(total_ms=latency_ms)
        _log_demo_result(
            mode="issue_diagnosis",
            config=config,
            request_id=request_id,
            session_id=session_id,
            source_type="fallback",
            latency_ms=latency_ms,
            fallback_reason=_fallback_reason(exc),
        )
        return response
    _log_demo_failure(
        mode="issue_diagnosis",
        config=config,
        request_id=request_id,
        session_id=session_id,
        status_code=_safe_error_status(exc),
        latency_ms=latency_ms,
        retryable=exc.retryable,
        fallback_available=config.demo_allow_sample_fallback,
        technical_detail=_technical_detail(exc),
    )
    _raise_demo_error(
        exc,
        fallback_available=config.demo_allow_sample_fallback,
    )


def _raise_demo_error(
    exc: ServingInvocationError,
    *,
    fallback_available: bool,
) -> NoReturn:
    status_code = _safe_error_status(exc)
    error = DemoError(
        code="retail_agent_unavailable",
        user_message="The live Agentic Commerce agent is unavailable. Try again.",
        technical_detail=_technical_detail(exc),
        retryable=exc.retryable,
        fallback_available=fallback_available,
    )
    raise DemoRouteError(status_code=status_code, error=error)


def _safe_error_status(exc: ServingInvocationError) -> int:
    if exc.status_code in {408, 504}:
        return 504
    if exc.status_code in {429, 503}:
        return 503
    return 502


def _technical_detail(exc: ServingInvocationError) -> str:
    detail = exc.detail or str(exc)
    return _redact_sensitive_text(detail).replace("\n", " ")[:1000]


def _redact_sensitive_text(value: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+",
        r"\1[REDACTED]",
        value,
    )
    redacted = re.sub(
        r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(neo4j[_-]?password\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def _fallback_reason(exc: ServingInvocationError) -> str:
    if exc.status_code is None:
        return str(exc)
    return f"{exc} status_code={exc.status_code}"


def _log_demo_result(
    *,
    mode: str,
    config: AppConfig,
    request_id: str,
    session_id: str,
    source_type: str,
    latency_ms: int | None,
    databricks_request_id: str | None = None,
    fallback_reason: str | None = None,
) -> None:
    logger.info(
        "demo_request mode=%s request_id=%s session_id=%s endpoint=%s "
        "source_type=%s latency_ms=%s databricks_request_id=%s fallback_reason=%s",
        mode,
        request_id,
        session_id,
        config.retail_agent_endpoint_name,
        source_type,
        latency_ms,
        databricks_request_id,
        fallback_reason,
    )


def _log_demo_failure(
    *,
    mode: str,
    config: AppConfig,
    request_id: str,
    session_id: str,
    status_code: int,
    latency_ms: int,
    retryable: bool,
    fallback_available: bool,
    technical_detail: str,
) -> None:
    logger.warning(
        "demo_request_failed mode=%s request_id=%s session_id=%s endpoint=%s "
        "status_code=%s latency_ms=%s retryable=%s fallback_available=%s "
        "technical_detail=%s",
        mode,
        request_id,
        session_id,
        config.retail_agent_endpoint_name,
        status_code,
        latency_ms,
        retryable,
        fallback_available,
        technical_detail,
    )
