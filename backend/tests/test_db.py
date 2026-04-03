from pathlib import Path

import sqlite3

import app.db as db


def test_serialize_deserialize_round_trip() -> None:
    board = {
        "columns": [
            {"id": "col-1", "title": "Todo", "cardIds": ["card-1"]},
            {"id": "col-2", "title": "Done", "cardIds": []},
        ],
        "cards": {
            "card-1": {
                "id": "card-1",
                "title": "Example task",
                "details": "Details for the task.",
            }
        },
    }

    payload = db.serialize_board(board)
    loaded = db.deserialize_board(payload)

    assert loaded == board


def test_deserialize_invalid_payload_returns_default() -> None:
    loaded_from_none = db.deserialize_board(None)
    loaded_from_invalid = db.deserialize_board("not-json")

    assert loaded_from_none == db.default_board()
    assert loaded_from_invalid == db.default_board()


def test_initialize_database_creates_file_and_tables(tmp_path: Path) -> None:
    test_db_path = tmp_path / "test-db.sqlite3"
    assert not test_db_path.exists()

    created_path = db.initialize_database(test_db_path)

    assert created_path == test_db_path
    assert test_db_path.exists()

    with sqlite3.connect(created_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "users" in tables
        assert "boards" in tables


def test_foreign_keys_enabled_on_connection(tmp_path: Path) -> None:
    test_db_path = tmp_path / "test-db.sqlite3"
    conn = db.get_connection(test_db_path)
    try:
        cursor = conn.execute("PRAGMA foreign_keys;")
        (value,) = cursor.fetchone()
        assert value == 1
    finally:
        conn.close()

