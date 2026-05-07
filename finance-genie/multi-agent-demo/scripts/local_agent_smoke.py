"""Run a local in-process smoke test against the graph specialist agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mlflow.types.responses import ResponsesAgentRequest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_settings  # noqa: E402
from finance_graph_supervisor_agent import AGENT  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="Prompt to send to the local agent")
    args = parser.parse_args()

    settings = load_settings()
    prompt = args.prompt or settings.smoke_test_prompt
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": prompt}],
    )
    response = AGENT.predict(request)
    print(json.dumps(response.model_dump(exclude_none=True), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
