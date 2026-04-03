from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.kanban_repo as kanban_repo
import app.main as main
from app.kanban_models import BoardModel


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


def test_repo_get_board_bootstraps_default(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite3"
    assert not db_path.exists()

    board = kanban_repo.get_board_for_user("user", db_path=db_path)

    assert db_path.exists()
    assert board["columns"][0]["id"] == "col-todo"
    assert board["cards"] == {}


def test_repo_save_board_persists_and_returns_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite3"

    original = kanban_repo.get_board_for_user("user", db_path=db_path)
    assert original["cards"] == {}

    new_board: BoardModel = BoardModel(
        columns=[
            {"id": "col-todo", "title": "Todo", "cardIds": ["card-1"]},
            {"id": "col-in-progress", "title": "In Progress", "cardIds": []},
            {"id": "col-done", "title": "Done", "cardIds": ["card-2"]},
        ],
        cards={
            "card-1": {
                "id": "card-1",
                "title": "Task 1",
                "details": "Details 1",
            },
            "card-2": {
                "id": "card-2",
                "title": "Task 2",
                "details": "Details 2",
            },
        },
    )

    saved = kanban_repo.save_board_for_user(
        "user", board_payload=new_board.model_dump(), db_path=db_path
    )

    assert saved == new_board.model_dump()
    assert kanban_repo.get_board_for_user("user", db_path=db_path) == new_board.model_dump()


def test_get_board_requires_auth(client: TestClient) -> None:
    response = client.get("/api/board")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_get_board_creates_db_on_first_use(client: TestClient, tmp_path: Path) -> None:
    # `client` points at `tmp_path/db.sqlite3` but we can't access that directly,
    # so we re-derive the expected path here.
    db_path = tmp_path / "db.sqlite3"
    assert not db_path.exists()

    login(client)
    response = client.get("/api/board")
    assert response.status_code == 200
    assert db_path.exists()


def test_put_board_requires_auth(client: TestClient) -> None:
    response = client.put("/api/board", json={"columns": [], "cards": {}})
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_put_board_valid_payload_persists_for_authenticated_user(client: TestClient) -> None:
    login(client)

    board: BoardModel = BoardModel(
        columns=[
            {"id": "col-todo", "title": "Todo", "cardIds": ["card-1"]},
            {"id": "col-in-progress", "title": "In Progress", "cardIds": ["card-2"]},
            {"id": "col-done", "title": "Done", "cardIds": []},
        ],
        cards={
            "card-1": {"id": "card-1", "title": "Task 1", "details": "D1"},
            "card-2": {"id": "card-2", "title": "Task 2", "details": "D2"},
        },
    )

    put_resp = client.put("/api/board", json=board.model_dump())
    assert put_resp.status_code == 200
    assert put_resp.json() == board.model_dump()

    get_resp = client.get("/api/board")
    assert get_resp.status_code == 200
    assert get_resp.json() == board.model_dump()


def test_put_board_rejects_inconsistent_payload(client: TestClient) -> None:
    login(client)

    # Referencing a cardId that doesn't exist in `cards`.
    response = client.put(
        "/api/board",
        json={
            "columns": [
                {"id": "col-todo", "title": "Todo", "cardIds": ["missing-card"]}
            ],
            "cards": {},
        },
    )
    assert response.status_code == 422


def test_put_board_rejects_card_id_key_mismatch(client: TestClient) -> None:
    login(client)

    response = client.put(
        "/api/board",
        json={
            "columns": [
                {"id": "col-todo", "title": "Todo", "cardIds": ["card-1"]}
            ],
            "cards": {"card-1": {"id": "different-id", "title": "T", "details": "D"}},
        },
    )
    assert response.status_code == 422

