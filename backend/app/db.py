from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DB_FILENAME = "db.sqlite3"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / DB_FILENAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path(override: Path | None = None) -> Path:
    """
    Resolve the database path.

    An override can be supplied for testing; in normal app usage the project-root
    `db.sqlite3` is used.
    """
    if override is not None:
        return override
    return DEFAULT_DB_PATH


def initialize_database(db_path: Path | None = None) -> Path:
    """
    Ensure the SQLite database file and core tables exist.

    This function is idempotent and safe to call multiple times.
    """
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                board_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

    return path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Get a SQLite connection, initializing the database if needed.
    """
    path = initialize_database(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def serialize_board(board: Dict[str, Any]) -> str:
    """
    Convert an in-memory board dictionary to a JSON string suitable for storage.
    """
    return json.dumps(board, sort_keys=True, separators=(",", ":"))


def deserialize_board(payload: str | None) -> Dict[str, Any]:
    """
    Convert a stored board JSON string back into a dictionary.

    If the payload is missing or invalid JSON, fall back to a simple default
    empty-board shape that matches the frontend `BoardData` structure.
    """
    if not payload:
        return default_board()

    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            return default_board()
        return data
    except json.JSONDecodeError:
        return default_board()


def default_board() -> Dict[str, Any]:
    """
    Minimal default board compatible with the frontend BoardData type.
    """
    return {
        "columns": [
            {"id": "col-todo", "title": "Todo", "cardIds": []},
            {"id": "col-in-progress", "title": "In Progress", "cardIds": []},
            {"id": "col-done", "title": "Done", "cardIds": []},
        ],
        "cards": {},
    }


def ensure_user_board(username: str, db_path: Path | None = None) -> None:
    """
    Helper used in later parts: ensure a user and their single board row exist.

    This is included here so later API work can rely on one board per user
    without re-implementing bootstrap behavior.
    """
    path = get_db_path(db_path)
    initialize_database(path)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        # `sqlite3.connect()` defaults to tuple rows; explicitly opt-in to
        # dict-like row access for this helper.
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id FROM users WHERE username = ?;",
            (username,),
        )
        row = cursor.fetchone()

        if row is None:
            created_at = _utc_now_iso()
            cursor = conn.execute(
                "INSERT INTO users (username, created_at) VALUES (?, ?);",
                (username, created_at),
            )
            user_id = cursor.lastrowid
            now = _utc_now_iso()
            conn.execute(
                """
                INSERT INTO boards (user_id, board_json, created_at, updated_at)
                VALUES (?, ?, ?, ?);
                """,
                (user_id, serialize_board(default_board()), now, now),
            )
        else:
            user_id = row["id"]
            cursor = conn.execute(
                "SELECT id FROM boards WHERE user_id = ?;",
                (user_id,),
            )
            board = cursor.fetchone()
            if board is None:
                now = _utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO boards (user_id, board_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?);
                    """,
                    (user_id, serialize_board(default_board()), now, now),
                )

