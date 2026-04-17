from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .db import deserialize_board, ensure_user_board, get_connection, serialize_board


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_board_for_user(username: str, db_path: Path | None = None) -> Dict[str, Any]:
    """
    Fetch the persisted board JSON for a user.

    If the user (or board row) doesn't exist yet, this bootstraps it from
    application defaults (Part 5 behavior).
    """
    ensure_user_board(username, db_path=db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT id FROM users WHERE username = ?;", (username,))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("User bootstrap failed — missing user row after ensure_user_board")

        cursor = conn.execute(
            "SELECT board_json FROM boards WHERE user_id = ?;",
            (row["id"],),
        )
        board_row = cursor.fetchone()
        if board_row is None:
            # Defensive: should not happen due to ensure_user_board.
            return {}
        return deserialize_board(board_row["board_json"])
    finally:
        conn.close()


def save_board_for_user(
    username: str, board_payload: Dict[str, Any], db_path: Path | None = None
) -> Dict[str, Any]:
    """
    Persist a full board payload for the user.
    """
    ensure_user_board(username, db_path=db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT id FROM users WHERE username = ?;", (username,))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("User bootstrap failed — missing user row after ensure_user_board")
        now = _utc_now_iso()
        conn.execute(
            """
            UPDATE boards
            SET board_json = ?, updated_at = ?
            WHERE user_id = ?;
            """,
            (serialize_board(board_payload), now, row["id"]),
        )
        conn.commit()
        return deserialize_board(serialize_board(board_payload))
    finally:
        conn.close()

