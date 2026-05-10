from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import ConsoleMessage, Page, Request, Response


APP_DIR = Path(__file__).resolve().parents[1]
SERVER_READY_TIMEOUT_SECONDS = 15

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + SERVER_READY_TIMEOUT_SECONDS
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(
                f"Analyst client exited before becoming ready.\n{output}"
            )

        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc

        time.sleep(0.2)

    raise RuntimeError(f"Analyst client did not become ready: {last_error}")


@pytest.fixture(scope="session")
def app_server() -> Generator[str]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "DATABRICKS_APP_PORT": str(port),
        "PYTHON_DOTENV_DISABLED": "1",
        "USE_MOCK_BACKEND": "true",
    }

    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_server(base_url, process)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="session")
def base_url(app_server: str) -> str:
    return app_server


@pytest.fixture(autouse=True)
def fail_on_browser_errors(page: Page, base_url: str) -> Generator[None]:
    errors: list[str] = []

    def on_console(message: ConsoleMessage) -> None:
        if message.type == "error":
            errors.append(f"console error: {message.text}")

    def on_page_error(error: Any) -> None:
        errors.append(f"page error: {error}")

    def on_request_failed(request: Request) -> None:
        errors.append(f"request failed: {request.url} {request.failure}")

    def on_response(response: Response) -> None:
        if not response.url.startswith(base_url):
            return
        if response.status >= 400 and not response.url.endswith("/favicon.ico"):
            errors.append(f"HTTP {response.status}: {response.url}")

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)

    yield

    assert errors == []
