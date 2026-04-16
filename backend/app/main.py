import logging
import os
import secrets
from pathlib import Path
from time import perf_counter, time

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import ValidationError

from .ai_client import AIClientError, openrouter_client_from_env
from .ai_chat_models import (
    AIChatRequestModel,
    AIChatResponseModel,
    AIChatStructuredOutputModel,
)
from .kanban_models import BoardModel
from . import kanban_repo

logger = logging.getLogger(__name__)

app = FastAPI(title="pm-backend", version="0.1.0")

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)

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
VALID_USERNAME = os.getenv("DEMO_USERNAME", "user")
VALID_PASSWORD = os.getenv("DEMO_PASSWORD", "password")
# Sessions stored as token -> expiry_timestamp. TTL of 8 hours.
SESSION_TTL_SECONDS = 8 * 60 * 60
active_sessions: dict[str, float] = {}

_is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _frontend_index() -> Path:
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return index
    return STATIC_INDEX


def _is_authenticated(request: Request) -> bool:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        return False
    expiry = active_sessions.get(session_token)
    if expiry is None:
        return False
    if time() > expiry:
        active_sessions.pop(session_token, None)
        return False
    return True


def _db_path_override() -> Path | None:
    # Test-only hook: lets us point the backend at a temp SQLite file.
    value = os.getenv("PM_DB_PATH")
    if not value:
        return None
    return Path(value)


def _authenticated_username(request: Request) -> str:
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # MVP limitation: only one demo user exists.
    return VALID_USERNAME


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
    active_sessions[session_token] = time() + SESSION_TTL_SECONDS

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        httponly=True,
        samesite="lax",
        secure=_is_production,
        path="/",
    )
    return response


@app.get("/logout")
def logout(request: Request) -> RedirectResponse:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        active_sessions.pop(session_token, None)

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


@app.get("/api/board", response_model=BoardModel)
def get_board(request: Request) -> dict[str, object]:
    username = _authenticated_username(request)
    return kanban_repo.get_board_for_user(
        username=username, db_path=_db_path_override()
    )  # already validated/serialized


@app.put("/api/board", response_model=BoardModel)
def put_board(request: Request, board: BoardModel) -> dict[str, object]:
    username = _authenticated_username(request)
    saved = kanban_repo.save_board_for_user(
        username=username, board_payload=board.model_dump(), db_path=_db_path_override()
    )
    return saved


@app.post("/api/ai/dev-connectivity")
def ai_dev_connectivity(request: Request) -> dict[str, object]:
    _authenticated_username(request)

    started = perf_counter()
    try:
        client = openrouter_client_from_env()
        response_text = client.complete("2+2")
    except AIClientError as exc:
        status_code, detail = exc.to_http()
        raise HTTPException(status_code=status_code, detail=detail) from exc

    elapsed_ms = int((perf_counter() - started) * 1000)
    return {
        "prompt": "2+2",
        "response": response_text,
        "model": client.model,
        "latencyMs": elapsed_ms,
    }


@app.post("/api/ai/chat", response_model=AIChatResponseModel)
def ai_chat(request: Request, payload: AIChatRequestModel) -> AIChatResponseModel:
    username = _authenticated_username(request)
    board = kanban_repo.get_board_for_user(username=username, db_path=_db_path_override())
    history_payload = [turn.model_dump() for turn in payload.history]

    try:
        client = openrouter_client_from_env()
        structured = client.complete_structured_chat(
            board_payload=board,
            user_message=payload.message,
            history=history_payload,
        )
        parsed = AIChatStructuredOutputModel.model_validate(structured)
    except AIClientError as exc:
        status_code, detail = exc.to_http()
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "ai_invalid_response",
                "message": "AI provider returned an invalid response.",
            },
        ) from exc

    board_update = parsed.boardUpdate
    if board_update is not None:
        saved_board = kanban_repo.save_board_for_user(
            username=username,
            board_payload=board_update.model_dump(),
            db_path=_db_path_override(),
        )
        board_update = BoardModel.model_validate(saved_board)

    return AIChatResponseModel(
        assistantMessage=parsed.assistantMessage,
        boardUpdate=board_update,
    )


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
