from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture(autouse=True)
def clear_sessions() -> None:
    main.active_sessions.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello_endpoint(client: TestClient) -> None:
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from FastAPI"}


def test_root_redirects_to_login_when_unauthenticated(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_renders(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in" in response.text
    assert 'name="username"' in response.text


def test_login_failure_redirects_with_error(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "wrong", "password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=1"


def test_login_success_sets_cookie_and_allows_root(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert main.SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")

    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers.get("content-type", "")


def test_logout_clears_session_and_redirects_to_login(client: TestClient) -> None:
    client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert client.get("/", follow_redirects=False).status_code == 200

    logout = client.get("/logout", follow_redirects=False)
    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"

    after_logout = client.get("/", follow_redirects=False)
    assert after_logout.status_code == 303
    assert after_logout.headers["location"] == "/login"


def test_frontend_asset_route_returns_index_for_unknown_path(
    tmp_path: Path, monkeypatch, client: TestClient
) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True)
    index = frontend_dir / "index.html"
    index.write_text("<html><body>Kanban Studio</body></html>", encoding="utf-8")

    monkeypatch.setattr(main, "FRONTEND_DIR", frontend_dir)

    client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.get("/some/deep/link")
    assert response.status_code == 200
    assert "Kanban Studio" in response.text


def test_frontend_asset_route_serves_real_file(
    tmp_path: Path, monkeypatch, client: TestClient
) -> None:
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir(parents=True)
    file_path = frontend_dir / "robots.txt"
    file_path.write_text("User-agent: *", encoding="utf-8")
    (frontend_dir / "index.html").write_text(
        "<html><body>Kanban Studio</body></html>", encoding="utf-8"
    )

    monkeypatch.setattr(main, "FRONTEND_DIR", frontend_dir)

    client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "User-agent: *" in response.text


def test_api_prefix_is_not_handled_by_frontend_catchall(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404


def test_expired_session_is_rejected(client: TestClient) -> None:
    import time as _time

    client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    # Manually expire all sessions.
    for token in list(main.active_sessions):
        main.active_sessions[token] = _time.time() - 1

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_board_api_rejects_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/board")
    assert response.status_code == 401


def test_login_with_env_override_credentials(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(main, "VALID_USERNAME", "envuser")
    monkeypatch.setattr(main, "VALID_PASSWORD", "envpass")

    bad = client.post(
        "/login",
        data={"username": "user", "password": "password"},
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert "error=1" in bad.headers["location"]

    good = client.post(
        "/login",
        data={"username": "envuser", "password": "envpass"},
        follow_redirects=False,
    )
    assert good.status_code == 303
    assert good.headers["location"] == "/"
