import os
import time

import redis
from flask import Flask, Response, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")
COMMIT_SHA = os.environ.get("COMMIT_SHA", "unknown")

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Nombre total de requetes HTTP recues",
    ["method", "endpoint", "code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Duree de traitement d'une requete HTTP, en secondes",
    ["method", "endpoint"],
)
BUILD_INFO = Gauge(
    "app_build_info",
    "Version et commit actuellement deployes",
    ["version", "commit_sha"],
)
BUILD_INFO.labels(version=APP_VERSION, commit_sha=COMMIT_SHA).set(1)


def get_redis_client():
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", 6379))
    return redis.Redis(host=host, port=port, decode_responses=True)


@app.before_request
def _start_timer():
    request._metrics_start = time.perf_counter()


@app.after_request
def _record_metrics(response):
    if request.path == "/metrics":
        return response
    endpoint = request.url_rule.rule if request.url_rule else "unmatched"
    duration = time.perf_counter() - request._metrics_start
    code = response.status_code
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, code=code).inc()
    REQUEST_DURATION.labels(method=request.method, endpoint=endpoint).observe(duration)
    return response


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/health")
def health():
    try:
        get_redis_client().ping()
    except redis.RedisError:
        return jsonify(status="error"), 503
    return jsonify(status="ok"), 200


@app.route("/status")
def status():
    return jsonify(
        service="devops-evaluation",
        version=APP_VERSION,
        commit_sha=COMMIT_SHA,
    ), 200


@app.route("/visits")
def visits():
    client = get_redis_client()
    count = client.incr("visits")
    return jsonify(visits=count), 200


@app.route("/simulate-error")
def simulate_error():
    return jsonify(status="error"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
