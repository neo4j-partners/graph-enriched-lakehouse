import os

from flask import Flask, jsonify, request, send_from_directory

USE_MOCK = os.getenv("USE_MOCK_BACKEND", "true").lower() == "true"
if USE_MOCK:
    from backend import MockBackend as Backend
else:
    from backend import RealBackend as Backend

backend = Backend()
app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/search", methods=["POST"])
def search():
    body = request.get_json()
    rings = backend.search(body["signal_type"], body.get("filters", {}))
    return jsonify(rings)


@app.route("/api/load", methods=["POST"])
def load():
    ring_ids = request.get_json()["ring_ids"]
    result = backend.load(ring_ids)
    return jsonify(result)


@app.route("/api/genie", methods=["POST"])
def genie():
    body = request.get_json()
    result = backend.ask_genie(body["question"], body.get("conversation_id"))
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
