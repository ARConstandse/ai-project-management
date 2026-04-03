import secrets
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

app = FastAPI(title="pm-backend", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_INDEX = STATIC_DIR / "index.html"
FRONTEND_DIR = STATIC_DIR / "frontend"
LOGIN_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sign in - PM MVP</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #f8f9fc;
        font-family: "Segoe UI", sans-serif;
        color: #032147;
      }
      main {
        width: min(420px, calc(100vw - 2rem));
        background: #ffffff;
        border: 1px solid rgba(3, 33, 71, 0.08);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 8px 24px rgba(3, 33, 71, 0.08);
      }
      h1 {
        margin: 0 0 0.5rem;
      }
      .muted {
        margin: 0 0 1rem;
        color: #888888;
      }
      label {
        display: block;
        margin: 0.75rem 0 0.25rem;
        font-size: 0.9rem;
      }
      input {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid rgba(3, 33, 71, 0.16);
        border-radius: 10px;
        padding: 0.6rem 0.75rem;
      }
      button {
        margin-top: 1rem;
        width: 100%;
        border: none;
        border-radius: 999px;
        padding: 0.7rem 1rem;
        background: #753991;
        color: #ffffff;
        font-weight: 600;
        cursor: pointer;
      }
      .error {
        margin-top: 0.5rem;
        color: #b42318;
        font-size: 0.9rem;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>Sign in</h1>
      <p class="muted">Use demo credentials to access the Kanban board.</p>
      <form method="post" action="/login">
        <label for="username">Username</label>
        <input id="username" name="username" autocomplete="username" required />
        <label for="password">Password</label>
        <input id="password" type="password" name="password" autocomplete="current-password" required />
        <button type="submit">Sign in</button>
      </form>
      __ERROR_BLOCK__
    </main>
  </body>
</html>
"""
SESSION_COOKIE_NAME = "pm_session"
VALID_USERNAME = "user"
VALID_PASSWORD = "password"
active_sessions: set[str] = set()


def _frontend_index() -> Path:
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return index
    return STATIC_INDEX


def _is_authenticated(request: Request) -> bool:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    return bool(session_token and session_token in active_sessions)


def _login_page(error: bool = False) -> str:
    error_block = "<p class='error'>Invalid username or password.</p>" if error else ""
    return LOGIN_TEMPLATE.replace("__ERROR_BLOCK__", error_block)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return _frontend_index().read_text(encoding="utf-8")


@app.get("/login", response_class=HTMLResponse)
def login_page(error: bool = False) -> str:
    return _login_page(error=error)


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    if username != VALID_USERNAME or password != VALID_PASSWORD:
        return RedirectResponse(url="/login?error=1", status_code=303)

    session_token = secrets.token_urlsafe(32)
    active_sessions.add(session_token)

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        active_sessions.discard(session_token)

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


@app.get("/{full_path:path}")
def frontend_assets(request: Request, full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    if FRONTEND_DIR.exists():
        candidate = FRONTEND_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)

        nested_index = candidate / "index.html"
        if nested_index.is_file():
            return FileResponse(nested_index)

        return FileResponse(_frontend_index())

    return FileResponse(_frontend_index())
