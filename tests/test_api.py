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
