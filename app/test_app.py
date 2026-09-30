import os

import redis

from app import app, get_redis_client


def _redis_available():
    try:
        get_redis_client().ping()
        return True
    except redis.RedisError:
        return False


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/health")
    if _redis_available():
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"
    else:
        assert response.status_code == 503
        assert response.get_json()["status"] == "error"


def test_status_endpoint():
    client = app.test_client()
    response = client.get("/status")
    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == "devops-evaluation"
    assert "commit_sha" in body


def test_visits_endpoint_increments():
    if not _redis_available():
        return
    redis_client = get_redis_client()
    redis_client.delete("visits")
    client = app.test_client()
    first = client.get("/visits").get_json()["visits"]
    second = client.get("/visits").get_json()["visits"]
    assert second == first + 1


def test_simulate_error_returns_500():
    client = app.test_client()
    response = client.get("/simulate-error")
    assert response.status_code == 500


def test_simulate_slow_returns_ok():
    client = app.test_client()
    response = client.get("/simulate-slow")
    assert response.status_code == 200


def test_metrics_endpoint_exposes_request_count():
    client = app.test_client()
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_metrics_excludes_itself_from_hook():
    client = app.test_client()
    client.get("/metrics")
    response = client.get("/metrics")
    body = response.get_data(as_text=True)
    assert 'endpoint="/metrics"' not in body


def test_commit_sha_env_var_reflected_in_build_info():
    response = app.test_client().get("/metrics")
    body = response.get_data(as_text=True)
    expected_sha = os.environ.get("COMMIT_SHA", "unknown")
    assert f'commit_sha="{expected_sha}"' in body
