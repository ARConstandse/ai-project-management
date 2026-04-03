---
title: Database schema and initialization
---

## Goals

- **Support multiple users** while the MVP UI still uses the hardcoded `user` / `password` login.
- **Enforce one Kanban board per user** in the database.
- **Store the Kanban board as JSON** so the backend can evolve with minimal migrations during the MVP.

## SQLite schema

All tables live in a single SQLite file named `db.sqlite3` at the project root.

### `users` table

- **Purpose**: represent an account that owns exactly one Kanban board.
- **Notes**: credentials are not read from this table in the MVP; the login continues to use the hardcoded demo credentials. This table prepares us for future real auth.

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `username TEXT NOT NULL UNIQUE`
- `created_at TEXT NOT NULL` — ISO 8601 timestamp in UTC

### `boards` table

- **Purpose**: persist a single board per user, with the full Kanban payload stored as JSON.
- **Constraint**: one row per user (enforced via a `UNIQUE` constraint on `user_id`).

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `user_id INTEGER NOT NULL UNIQUE` — references `users.id`
- `board_json TEXT NOT NULL` — serialized board payload
- `created_at TEXT NOT NULL` — ISO 8601 timestamp in UTC
- `updated_at TEXT NOT NULL` — ISO 8601 timestamp in UTC

Foreign key:

- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`

### Board JSON shape

The `board_json` column stores a payload compatible with the existing frontend `BoardData` type:

- `columns: { id: string; title: string; cardIds: string[] }[]`
- `cards: Record<string, { id: string; title: string; details: string }>`

We intentionally store the board as a single JSON document to keep the schema simple during the MVP. Future versions can normalize cards/columns into separate tables if needed.

## Initialization and migration behavior

- **DB location**: `db.sqlite3` is created automatically on first access if it does not exist.
- **Initialization**:
  - The backend includes a small `db` module responsible for:
    - Creating the SQLite file (if missing).
    - Running `CREATE TABLE IF NOT EXISTS` statements for `users` and `boards`.
    - Enabling foreign keys (`PRAGMA foreign_keys = ON`).
  - Initialization is idempotent and safe to call on every process start.
- **Migrations**:
  - For the MVP there is no migration framework; schema changes, if needed, will be handled manually.
  - Because the board is stored as JSON, most early changes to the board shape can be handled in application code without altering the SQL schema.

## Trade-offs

- **Pros**:
  - Very small schema surface area (two tables).
  - One-row-per-user constraint keeps the MVP aligned with “single board per user”.
  - JSON payload mirrors the existing frontend board model, reducing mapping logic.
  - Simple initialization without a heavy migration tool.
- **Cons**:
  - Harder to query across boards/cards (e.g., “all cards in progress”) because data is nested in JSON.
  - Future features like multi-board support or advanced analytics will likely require schema changes.
  - Manual migrations may be needed if we outgrow the JSON-in-a-row approach.

## Testing strategy

- **Unit tests**:
  - Verify board serialization/deserialization round-trips between Python dicts and JSON strings.
  - Ensure safe defaults (e.g., returning a reasonable empty/default board when on-disk data is missing or invalid).
- **Integration tests**:
  - Use a temporary SQLite file path and assert that:
    - The DB file is created when missing.
    - `users` and `boards` tables exist with the expected constraints.
    - Foreign keys are enabled.

