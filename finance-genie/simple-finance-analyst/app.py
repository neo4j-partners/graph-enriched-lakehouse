import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

APP_DIR = Path(__file__).resolve().parent
ROOT_ENV = APP_DIR.parent / ".env"
LOCAL_ENV = APP_DIR / ".env"

load_dotenv(ROOT_ENV, override=False)
load_dotenv(LOCAL_ENV, override=False)

USE_MOCK = os.getenv("USE_MOCK_BACKEND", "true").lower() == "true"
if USE_MOCK:
    from backend import MockBackend as Backend
else:
    from backend import RealBackend as Backend

backend = Backend()
app = Flask(__name__, static_folder="static", static_url_path="")


def _json_body() -> dict | None:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _bad_request(message: str):
    return jsonify({"error": message}), 400


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search", methods=["POST"])
def search():
    body = _json_body()
    if body is None:
        return _bad_request("Request body must be a JSON object.")

    signal_type = body.get("signal_type")
    if not isinstance(signal_type, str) or not signal_type.strip():
        return _bad_request("signal_type is required.")

    filters = body.get("filters", {})
    if not isinstance(filters, dict):
        return _bad_request("filters must be an object.")

    rings = backend.search(signal_type, filters)
    return jsonify(rings)


@app.route("/api/load", methods=["POST"])
def load():
    body = _json_body()
    if body is None:
        return _bad_request("Request body must be a JSON object.")

    ring_ids = body.get("ring_ids")
    if (
        not isinstance(ring_ids, list)
        or not ring_ids
        or not all(isinstance(ring_id, str) and ring_id.strip() for ring_id in ring_ids)
    ):
        return _bad_request("ring_ids must be a non-empty list of strings.")

    result = backend.load(ring_ids)
    return jsonify(result)


@app.route("/api/genie", methods=["POST"])
def genie():
    body = _json_body()
    if body is None:
        return _bad_request("Request body must be a JSON object.")

    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        return _bad_request("question is required.")

    conversation_id = body.get("conversation_id")
    if conversation_id is not None and not isinstance(conversation_id, str):
        return _bad_request("conversation_id must be a string when provided.")

    result = backend.ask_genie(question, conversation_id)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
