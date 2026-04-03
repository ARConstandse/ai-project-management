from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai_client import OpenRouterClient
from app.ai_client import OPENROUTER_MODEL
from app.ai_client import AIClientError
import app.main as main


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    main.active_sessions.clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "db.sqlite3"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))
    return TestClient(main.app)


def login(client: TestClient) -> None:
    client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )


def test_ai_connectivity_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/dev-connectivity")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_ai_connectivity_returns_response_for_authenticated_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "4"}}]},
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    transport = httpx.MockTransport(handler)

    def fake_client_from_env() -> OpenRouterClient:
        return OpenRouterClient(api_key="fake-key", transport=transport)

    monkeypatch.setattr(main, "openrouter_client_from_env", fake_client_from_env)
    login(client)
    response = client.post("/api/ai/dev-connectivity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["prompt"] == "2+2"
    assert payload["response"] == "4"
    assert payload["model"] == OPENROUTER_MODEL
    assert isinstance(payload["latencyMs"], int)


def test_ai_connectivity_maps_timeout_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    class _TimeoutClient:
        def complete(self, prompt: str) -> str:
            raise AIClientError("timeout", "Upstream call timed out.")

    def fake_client_from_env() -> object:
        return _TimeoutClient()

    monkeypatch.setattr(main, "openrouter_client_from_env", fake_client_from_env)
    login(client)
    response = client.post("/api/ai/dev-connectivity")

    assert response.status_code == 504
    assert response.json() == {
        "detail": {"error": "ai_timeout", "message": "AI provider timed out."}
    }
