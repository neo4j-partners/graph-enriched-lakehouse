"""MLflow GenAI evaluation gate for the deployed demo contract.

This module evaluates the demo-client backend contract, not just raw prose. It
can score precomputed outputs from JSONL or call a deployed Databricks App when
an app URL is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

import mlflow
import mlflow.genai
from mlflow.entities import Feedback
from mlflow.genai.scorers import Guidelines, Safety, scorer


DEFAULT_EVAL_DATA = [
    {
        "inputs": {
            "mode": "agentic_search",
            "prompt": "waterproof trail running shoes under 150 dollars",
        }
    },
    {
        "inputs": {
            "mode": "issue_diagnosis",
            "prompt": (
                "My running shoes feel flat after 300 miles. "
                "What should I check?"
            ),
        }
    },
]


@scorer
def live_backend_contract(inputs: dict, outputs: dict) -> Feedback:
    """Require live backend output and live trace metadata."""
    mode = inputs.get("mode")
    source_type = outputs.get("source_type")
    trace_source = outputs.get("trace_source")
    passed = source_type == "live" and trace_source == "live"

    if mode == "agentic_search":
        passed = passed and outputs.get("product_count", 0) > 0
        requirement = "live search with at least one product card"
    elif mode == "issue_diagnosis":
        passed = passed and (
            outputs.get("knowledge_chunk_count", 0) > 0
            or outputs.get("cited_source_count", 0) > 0
            or outputs.get("recommended_action_count", 0) > 0
        )
        requirement = "live diagnosis with retrieved context or actions"
    else:
        passed = False
        requirement = f"recognized mode, got {mode!r}"

    return Feedback(
        name="live_backend_contract",
        value=passed,
        rationale=(
            f"Expected {requirement}; got source_type={source_type!r}, "
            f"trace_source={trace_source!r}."
        ),
    )


@scorer
def no_secret_leak(outputs: dict) -> Feedback:
    """Reject obvious credential material in user-visible outputs."""
    text = json.dumps(outputs, default=str).lower()
    blocked_markers = [
        "authorization:",
        "bearer ",
        "neo4j_password",
        "neo4j-password",
        "databricks_token",
        "access_token",
    ]
    leaks = [marker for marker in blocked_markers if marker in text]
    return Feedback(
        name="no_secret_leak",
        value=not leaks,
        rationale=(
            "No credential markers found."
            if not leaks
            else f"Found credential markers: {', '.join(leaks)}"
        ),
    )


def app_predict_fn(
    *,
    app_url: str,
    token: str | None,
    timeout_seconds: int,
):
    """Build a predict_fn that matches mlflow.genai.evaluate kwargs semantics."""

    def predict_fn(
        prompt: str,
        mode: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        session = session_id or f"eval-{uuid4()}"
        payload = {
            "prompt": prompt,
            "session_id": session,
            "user_id": user_id or f"session:{session}",
        }
        if mode == "agentic_search":
            route = "/api/demo/search"
        elif mode == "issue_diagnosis":
            route = "/api/demo/diagnose"
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            f"{app_url.rstrip('/')}{route}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            return {
                "response": f"HTTP {exc.code}",
                "source_type": "error",
                "trace_source": "unavailable",
                "error": detail,
            }

        return summarize_demo_response(body, int((time.perf_counter() - started) * 1000))

    return predict_fn


def summarize_demo_response(body: dict[str, Any], latency_ms: int | None = None) -> dict[str, Any]:
    """Flatten the demo API response into stable fields for evaluation."""
    return {
        "response": body.get("answer") or body.get("summary") or "",
        "mode": body.get("mode"),
        "source_type": body.get("source_type"),
        "trace_source": body.get("trace_source"),
        "request_id": body.get("request_id"),
        "databricks_request_id": body.get("databricks_request_id"),
        "latency_ms": latency_ms,
        "product_count": len(body.get("product_picks") or []),
        "related_product_count": len(body.get("related_products") or []),
        "knowledge_chunk_count": len(body.get("knowledge_chunks") or []),
        "cited_source_count": len(body.get("cited_sources") or []),
        "recommended_action_count": len(body.get("recommended_actions") or []),
        "memory_write_count": len(body.get("memory_writes") or []),
        "tool_timeline_count": len(body.get("tool_timeline") or []),
        "warning_count": len(body.get("warnings") or []),
    }


def load_eval_data(path: Path | None) -> list[dict[str, Any]]:
    """Load JSONL records or return the default representative demo prompts."""
    if path is None:
        return DEFAULT_EVAL_DATA

    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if "inputs" not in record:
                raise ValueError(f"{path}:{line_number} is missing required inputs")
            records.append(record)
    return records


def build_scorers(include_judges: bool, judge_model: str | None) -> list[Any]:
    scorers: list[Any] = [live_backend_contract, no_secret_leak]
    if include_judges:
        model_kwargs = {"model": f"databricks:/{judge_model}"} if judge_model else {}
        scorers.extend(
            [
                Safety(**model_kwargs),
                Guidelines(
                    name="retail_answer_quality",
                    guidelines=(
                        "The response must answer the retail customer request, "
                        "stay grounded in the retrieved product or support context, "
                        "and avoid claiming unavailable inventory or policy facts."
                    ),
                    **model_kwargs,
                ),
            ]
        )
    return scorers


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default=os.environ.get("AGENTIC_COMMERCE_EVAL_APP_URL"))
    parser.add_argument("--token-env", default="DATABRICKS_TOKEN")
    parser.add_argument("--data-jsonl", type=Path)
    parser.add_argument("--experiment", default=os.environ.get("MLFLOW_EXPERIMENT_NAME"))
    parser.add_argument("--tracking-uri", default=os.environ.get("MLFLOW_TRACKING_URI", "databricks"))
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--include-judges", action="store_true")
    parser.add_argument("--judge-model", default=os.environ.get("AGENTIC_COMMERCE_EVAL_JUDGE_MODEL"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    eval_data = load_eval_data(args.data_jsonl)

    mlflow.set_tracking_uri(args.tracking_uri)
    if args.experiment:
        mlflow.set_experiment(args.experiment)

    token = os.environ.get(args.token_env)
    missing_outputs = any("outputs" not in record for record in eval_data)
    predict_fn = None
    if missing_outputs:
        if not args.app_url:
            raise ValueError(
                "An app URL is required when any evaluation record omits outputs."
            )
        predict_fn = app_predict_fn(
            app_url=args.app_url,
            token=token,
            timeout_seconds=args.timeout_seconds,
        )

    results = mlflow.genai.evaluate(
        data=eval_data,
        predict_fn=predict_fn,
        scorers=build_scorers(args.include_judges, args.judge_model),
    )
    print(json.dumps({"run_id": results.run_id, "metrics": results.metrics}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
