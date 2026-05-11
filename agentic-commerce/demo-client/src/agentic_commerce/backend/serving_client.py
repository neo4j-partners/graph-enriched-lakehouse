from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from databricks.sdk import WorkspaceClient

from .core._config import AppConfig


class ServingInvocationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.detail = detail


@dataclass(frozen=True)
class ServingInvocationResult:
    payload: dict[str, Any]
    databricks_request_id: str | None
    latency_ms: int


def invoke_retail_agent(
    *,
    ws: WorkspaceClient,
    config: AppConfig,
    prompt: str,
    session_id: str,
    user_id: str | None,
    demo_mode: str,
) -> ServingInvocationResult:
    host = getattr(ws.config, "host", None)
    if not host:
        raise ServingInvocationError(
            "Databricks workspace host is not configured.",
            retryable=False,
        )

    endpoint_url = (
        f"{host.rstrip('/')}/serving-endpoints/"
        f"{config.retail_agent_endpoint_name}/invocations"
    )
    custom_inputs: dict[str, Any] = {
        "session_id": session_id,
        "demo_mode": demo_mode,
    }
    if user_id:
        custom_inputs["user_id"] = user_id

    body = json.dumps(
        {
            "messages": [{"role": "user", "content": prompt}],
            "custom_inputs": custom_inputs,
        }
    ).encode("utf-8")

    # WorkspaceClient.serving_endpoints.query does not expose ChatAgent
    # custom_inputs, so this path posts the Databricks invocation shape
    # directly while still using WorkspaceClient for host and auth.
    try:
        auth_headers = ws.config.authenticate()
    except Exception as exc:
        raise ServingInvocationError(
            "Databricks authentication failed.",
            retryable=False,
            detail=str(exc),
        ) from exc

    headers = {
        "Content-Type": "application/json",
        **auth_headers,
    }
    request = urllib.request.Request(
        endpoint_url,
        data=body,
        headers=headers,
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            request,
            timeout=config.retail_agent_timeout_seconds,
        ) as response:
            response_body = response.read().decode("utf-8")
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ServingInvocationResult(
                payload=_json_object(response_body),
                databricks_request_id=_request_id(dict(response.headers)),
                latency_ms=latency_ms,
            )
    except (TimeoutError, socket.timeout) as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        raise ServingInvocationError(
            "Retail agent invocation timed out.",
            status_code=504,
            retryable=True,
            detail=f"Timed out after {latency_ms} ms.",
        ) from exc
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ServingInvocationError(
            "Retail agent invocation failed.",
            status_code=exc.code,
            retryable=exc.code in {408, 429, 500, 502, 503, 504},
            detail=body_text[:1000],
        ) from exc
    except urllib.error.URLError as exc:
        timeout = isinstance(exc.reason, (TimeoutError, socket.timeout))
        message = (
            "Retail agent invocation timed out."
            if timeout
            else "Could not reach the Agentic Commerce agent endpoint."
        )
        raise ServingInvocationError(
            message,
            status_code=504 if timeout else None,
            retryable=True,
            detail=str(exc.reason),
        ) from exc


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ServingInvocationError(
            "Retail agent returned malformed JSON.",
            retryable=False,
            detail=value[:1000],
        ) from exc
    if not isinstance(parsed, dict):
        raise ServingInvocationError(
            "Retail agent returned an unexpected response shape.",
            retryable=False,
            detail=value[:1000],
        )
    return parsed


def _request_id(headers: dict[str, str]) -> str | None:
    for key in (
        "x-databricks-request-id",
        "x-request-id",
        "request-id",
    ):
        for actual_key, value in headers.items():
            if actual_key.lower() == key:
                return value
    return None
