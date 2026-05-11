"""Utility for sending queries to the deployed agent endpoint.

Shared by the endpoint demo and knowledge-check entry points. Handles auth
resolution, response parsing, message sending, endpoint readiness checks, and
keyword-validated exercise runs.
"""

from __future__ import annotations

import os

import requests

from retail_agent.agent.config import CONFIG


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def get_workspace_url_and_token() -> tuple[str, str]:
    """Get Databricks workspace URL and auth token.

    Tries dbutils (notebook), then WorkspaceClient (CLI/jobs),
    then environment variables.
    """
    # Method 1: dbutils notebook context
    try:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
        url = ctx.apiUrl().get().rstrip("/")
        token = ctx.apiToken().get()
        if url and token:
            return url, token
    except Exception:
        pass

    # Method 2: WorkspaceClient config
    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        url = (w.config.host or "").rstrip("/")
        token = w.config.token or ""
        if url and token:
            return url, token
    except Exception:
        pass

    # Method 3: Environment variables
    url = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if url and token:
        return url, token

    raise ValueError("Could not determine Databricks workspace URL and token")


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def extract_content(result: dict) -> str | None:
    """Extract text content from a ChatAgent or standard response.

    ChatAgent format:  {"messages": [{"role": "assistant", "content": "..."}]}
    Standard format:   {"choices": [{"message": {"content": "..."}}]}
    ResponsesAgent:    {"output": [{"type": "message", "content": [{"type": "output_text", "text": "..."}]}]}
    """
    # ChatAgent format
    if "messages" in result and result["messages"]:
        last = result["messages"][-1]
        return last.get("content", str(last))

    # Standard completion format
    if "choices" in result and result["choices"]:
        return result["choices"][0]["message"]["content"]

    # ResponsesAgent format
    if "output" in result:
        for item in result.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        return part.get("text")

    return None


# ---------------------------------------------------------------------------
# Endpoint readiness
# ---------------------------------------------------------------------------


def ensure_endpoint_ready() -> tuple[str, dict[str, str]]:
    """Check that the agent endpoint is READY and return (endpoint_url, headers).

    Raises RuntimeError if the endpoint is not found or not ready.
    Raises ValueError if auth cannot be resolved.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import EndpointStateReady

    w = WorkspaceClient()
    endpoint_name = CONFIG.resolved_endpoint_name

    print(f"Checking endpoint: {endpoint_name}")
    try:
        endpoint = w.serving_endpoints.get(endpoint_name)
        state = endpoint.state.ready if endpoint.state else None
        print(f"  Status: {state}")
    except Exception as e:
        raise RuntimeError(f"Endpoint not found: {e}") from e

    if state != EndpointStateReady.READY:
        raise RuntimeError("Endpoint is not ready yet — re-run once it reaches READY state.")

    workspace_url, token = get_workspace_url_and_token()
    endpoint_url = f"{workspace_url}/serving-endpoints/{endpoint_name}/invocations"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return endpoint_url, headers


# ---------------------------------------------------------------------------
# Message sending
# ---------------------------------------------------------------------------


def send_message(
    endpoint_url: str,
    headers: dict,
    query: str,
    custom_inputs: dict | None = None,
    timeout: int = 120,
    history: list[dict] | None = None,
) -> str | None:
    """Send a message to the endpoint and return extracted text.

    Args:
        history: Optional list of prior messages (user/assistant dicts).
            When provided, the full conversation history is sent so the
            agent has multi-turn context.
    """
    if history is not None:
        messages = history + [{"role": "user", "content": query}]
    else:
        messages = [{"role": "user", "content": query}]
    payload: dict = {"messages": messages}
    if custom_inputs:
        payload["custom_inputs"] = custom_inputs
    resp = requests.post(endpoint_url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return extract_content(resp.json())


# ---------------------------------------------------------------------------
# Exercise runner
# ---------------------------------------------------------------------------


def run_exercise(
    endpoint_url: str,
    headers: dict,
    turns: list[tuple[str, str, list[str]]],
    custom_inputs: dict | None = None,
    response_limit: int = 400,
    accumulate_history: bool = False,
) -> tuple[int, int]:
    """Run a keyword-validated exercise against the endpoint.

    Args:
        turns: List of (query, concept_label, expected_keywords) tuples.
        custom_inputs: Optional dict passed to every message (e.g. session_id).
        response_limit: Max characters to print from each response.
        accumulate_history: When True, each turn includes the full
            conversation history from prior turns, giving the agent
            multi-turn context (like a real chat session).

    Returns:
        (passed, failed) counts.
    """
    passed = 0
    failed = 0
    history: list[dict] = []

    for i, (query, concept, expected_keywords) in enumerate(turns, 1):
        print(f"\n  [{i}/{len(turns)}] {concept}")
        print(f"  Q: {query}")
        try:
            text = send_message(
                endpoint_url, headers, query, custom_inputs,
                history=history if accumulate_history else None,
            )
            if text is None:
                print("  FAIL — no response text")
                failed += 1
                if accumulate_history:
                    history.append({"role": "user", "content": query})
                continue

            if accumulate_history:
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": text})

            print(f"  A: {text[:response_limit]}")

            # Check for expected keywords (case-insensitive, ignore markdown)
            text_plain = text.lower().replace("*", "").replace("_", "")
            missing = [kw for kw in expected_keywords if kw.lower() not in text_plain]
            if missing:
                print(f"  FAIL — missing keywords: {missing}")
                failed += 1
            else:
                print("  PASS")
                passed += 1

        except requests.exceptions.HTTPError as e:
            print(f"  FAIL — HTTP {e.response.status_code}: {e.response.text[:200]}")
            failed += 1
        except Exception as e:
            print(f"  FAIL — {type(e).__name__}: {e}")
            failed += 1

    return passed, failed
