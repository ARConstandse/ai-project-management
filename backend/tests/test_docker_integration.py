import os
import shutil
import subprocess
import time

import httpx
import pytest


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.mark.integration
def test_container_serves_root_and_api() -> None:
    if not _docker_available():
        pytest.skip("docker is not installed")
    if os.getenv("RUN_DOCKER_INTEGRATION") != "1":
        pytest.skip("set RUN_DOCKER_INTEGRATION=1 to run docker integration tests")

    up_cmd = ["docker", "compose", "up", "--build", "-d"]
    down_cmd = ["docker", "compose", "down", "--remove-orphans", "--volumes"]
    subprocess.run(up_cmd, cwd=ROOT_DIR, check=True)
    try:
        deadline = time.time() + 90
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                health = httpx.get("http://127.0.0.1:8000/api/health", timeout=5)
                if health.status_code == 200 and health.json() == {"status": "ok"}:
                    break
            except Exception as exc:  # pragma: no cover - retry loop behavior
                last_error = exc
            time.sleep(1)
        else:
            if last_error:
                raise last_error
            raise AssertionError("container did not become healthy before timeout")

        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
            login_redirect = client.get("/", follow_redirects=False)
            assert login_redirect.status_code == 303
            assert login_redirect.headers.get("location") == "/login"

            login_page = client.get("/login")
            assert login_page.status_code == 200
            assert "Sign in" in login_page.text

            bad_login = client.post(
                "/login",
                data={"username": "bad", "password": "bad"},
                follow_redirects=False,
            )
            assert bad_login.status_code == 303
            assert bad_login.headers.get("location") == "/login?error=1"

            good_login = client.post(
                "/login",
                data={"username": "user", "password": "password"},
                follow_redirects=False,
            )
            assert good_login.status_code == 303
            assert good_login.headers.get("location") == "/"

            root = client.get("/")
            hello = client.get("/api/hello")
            assert root.status_code == 200
            assert "Kanban Studio" in root.text
            assert 'data-testid="column-' in root.text
            assert hello.status_code == 200
            assert hello.json() == {"message": "Hello from FastAPI"}

            logout = client.get("/logout", follow_redirects=False)
            assert logout.status_code == 303
            assert logout.headers.get("location") == "/login"

            root_after_logout = client.get("/", follow_redirects=False)
            assert root_after_logout.status_code == 303
            assert root_after_logout.headers.get("location") == "/login"
    finally:
        subprocess.run(down_cmd, cwd=ROOT_DIR, check=False)
