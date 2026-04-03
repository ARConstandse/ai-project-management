from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def test_ai_chat_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/chat", json={"message": "hello", "history": []})
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_ai_chat_response_only_output(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def complete_structured_chat(
            self, board_payload: dict[str, object], user_message: str, history: list[dict[str, str]]
        ) -> dict[str, object]:
            return {"assistantMessage": "No board changes needed.", "boardUpdate": None}

    monkeypatch.setattr(main, "openrouter_client_from_env", lambda: _FakeClient())
    login(client)
    response = client.post(
        "/api/ai/chat",
        json={"message": "summarize", "history": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "assistantMessage": "No board changes needed.",
        "boardUpdate": None,
    }


def test_ai_chat_response_and_board_update_output(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeClient:
        def complete_structured_chat(
            self, board_payload: dict[str, object], user_message: str, history: list[dict[str, str]]
        ) -> dict[str, object]:
            return {
                "assistantMessage": "Updated board.",
                "boardUpdate": {
                    "columns": [{"id": "col-todo", "title": "Todo", "cardIds": ["card-1"]}],
                    "cards": {
                        "card-1": {
                            "id": "card-1",
                            "title": "New title",
                            "details": "New details",
                        }
                    },
                },
            }

    monkeypatch.setattr(main, "openrouter_client_from_env", lambda: _FakeClient())
    login(client)
    response = client.post("/api/ai/chat", json={"message": "update board", "history": []})
    assert response.status_code == 200
    assert response.json()["assistantMessage"] == "Updated board."
    assert response.json()["boardUpdate"]["cards"]["card-1"]["title"] == "New title"

    board_response = client.get("/api/board")
    assert board_response.status_code == 200
    assert board_response.json()["cards"]["card-1"]["title"] == "New title"


def test_ai_chat_invalid_schema_does_not_corrupt_board(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeClient:
        def complete_structured_chat(
            self, board_payload: dict[str, object], user_message: str, history: list[dict[str, str]]
        ) -> dict[str, object]:
            return {
                "assistantMessage": "Attempted update",
                "boardUpdate": {
                    "columns": [{"id": "col-todo", "title": "Todo", "cardIds": ["missing-card"]}],
                    "cards": {},
                },
            }

    monkeypatch.setattr(main, "openrouter_client_from_env", lambda: _FakeClient())
    login(client)
    board_before = client.get("/api/board").json()

    response = client.post("/api/ai/chat", json={"message": "break it", "history": []})
    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "error": "ai_invalid_response",
            "message": "AI provider returned an invalid response.",
        }
    }

    board_after = client.get("/api/board").json()
    assert board_after == board_before
