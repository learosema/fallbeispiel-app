"""Login über den Proxy-Header (nur KI-Bewertung), Begrenzung der KI-Bewertungen, Obergrenze für das Protokoll."""
import pytest
from fastapi.testclient import TestClient

from backend import main

client = TestClient(main.app)
TOO_LONG = {"scenario": "x", "log": [{"t": i, "text": "a" * 1000} for i in range(31)]}


def test_without_auth_header_everyone_is_local(monkeypatch):
    monkeypatch.delenv("AUTH_HEADER", raising=False)
    assert client.post("/api/turn", json=TOO_LONG).status_code == 400  # kein 401: nur die Größe stört


def test_feedback_requires_login_when_configured(monkeypatch):
    monkeypatch.setenv("AUTH_HEADER", "X-Forwarded-Email")
    res = client.post("/api/feedback", json={"scenario": "x", "log": [{"t": 0, "text": "Hallo"}]})
    assert res.status_code == 401
    assert "angemeldet" in res.json()["error"]


def test_feedback_accepts_login(monkeypatch):
    monkeypatch.setenv("AUTH_HEADER", "X-Forwarded-Email")
    res = client.post("/api/feedback", json=TOO_LONG, headers={"X-Forwarded-Email": "a@example.org"})
    assert res.status_code == 400  # an der Anmeldung vorbei, scheitert erst an der Größe


@pytest.mark.parametrize("path", ["/api/turn", "/api/debrief"])
def test_simulation_and_checklist_need_no_login(monkeypatch, path):
    monkeypatch.setenv("AUTH_HEADER", "X-Forwarded-Email")
    assert client.post(path, json=TOO_LONG).status_code == 400  # kein 401


@pytest.mark.parametrize("n", [29, 30])
def test_log_size_limit(n):
    req = {"scenario": "x", "log": [{"t": i, "text": "a" * 1000} for i in range(n)]}
    main.RunRequest.model_validate(req)  # bis MAX_LOG_CHARS erlaubt


def test_rate_limit_per_user(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    limit = main.RateLimit(2, 3600)
    assert limit.hit("a") and limit.hit("a")
    assert not limit.hit("a")
    assert limit.hit("b")  # andere Person, eigenes Kontingent
    clock[0] = 3601
    assert limit.hit("a")  # Fenster abgelaufen


def test_feedback_rate_limited(monkeypatch):
    monkeypatch.delenv("AUTH_HEADER", raising=False)
    monkeypatch.setattr(main, "feedback_limit", main.RateLimit(0, 3600))
    res = client.post("/api/feedback", json={"scenario": "x", "log": [{"t": 0, "text": "Hallo"}]})
    assert res.status_code == 429
