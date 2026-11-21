"""API-Grenzen: Obergrenze für das Protokoll, alles ohne Anmeldung erreichbar."""
import pytest
from fastapi.testclient import TestClient

from backend import main

client = TestClient(main.app)
TOO_LONG = {"scenario": "x", "log": [{"t": i, "text": "a" * 1000} for i in range(31)]}


@pytest.mark.parametrize("path", ["/api/turn", "/api/debrief"])
def test_oversized_log_is_rejected(path):
    assert client.post(path, json=TOO_LONG).status_code == 400


@pytest.mark.parametrize("n", [29, 30])
def test_log_size_limit(n):
    req = {"scenario": "x", "log": [{"t": i, "text": "a" * 1000} for i in range(n)]}
    main.RunRequest.model_validate(req)  # bis MAX_LOG_CHARS erlaubt


def test_ai_feedback_is_gone():
    assert client.post("/api/feedback", json={"scenario": "x", "log": [{"t": 0, "text": "Hallo"}]}).status_code in (404, 405)


def test_rate_limit_per_client(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    limit = main.RateLimit(2, 60)
    assert limit.hit("a") and limit.hit("a")
    assert not limit.hit("a")
    assert limit.hit("b")  # andere IP, eigenes Kontingent
    clock[0] = 61
    assert limit.hit("a")  # Fenster abgelaufen
    assert main.RateLimit(0, 60).hit("a")  # 0 = aus


def test_api_is_rate_limited(monkeypatch):
    monkeypatch.setattr(main, "api_limit", main.RateLimit(1, 60))
    assert client.post("/api/turn", json=TOO_LONG).status_code == 400
    res = client.post("/api/turn", json=TOO_LONG)
    assert res.status_code == 429 and res.headers["Retry-After"] == "60"
    assert client.get("/").status_code == 200  # statische Dateien sind nicht begrenzt
