# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This App Does

Full-stack Kanban project management app with an AI chat sidebar. Users log in, manage cards across columns via drag-and-drop, and use natural language to create/move/edit cards via an AI assistant (OpenRouter). Single-user per container; board state is persisted to SQLite.

## Commands

### Running the app

```bash
# Docker (production-like, port 8000)
docker-compose up --build

# Local dev — backend (from backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Local dev — frontend (from frontend/, runs on port 3000)
npm run dev
```

Default credentials: `user` / `password`

Required env var: `OPENROUTER_API_KEY` (for AI chat)

### Testing

```bash
# Backend (from backend/)
pytest                     # all tests except integration
pytest -m integration      # integration tests only
pytest --cov=app           # coverage report (80% minimum required)

# Frontend (from frontend/)
npm run test:unit          # Vitest unit tests
npm run test:e2e           # Playwright end-to-end
npm run test:all           # both
```

Integration tests override the DB path via `PM_DB_PATH` env var (temporary file).

### Linting

```bash
# Frontend (from frontend/)
npm run lint
# Backend uses Ruff (no CLI command configured; runs via editor)
```

### Build (for Docker)

The Dockerfile does a multi-stage build: Node builds the Next.js frontend, then the output is copied into `backend/app/static/frontend/` so FastAPI serves it as static files.

## Architecture

### Request flow

```
Browser → FastAPI (port 8000)
  ├── Unauthenticated → /login (session cookie: pm_session)
  ├── GET / → serves built Next.js index.html
  ├── GET /api/board → returns user's board JSON
  ├── PUT /api/board → saves board JSON
  └── POST /api/ai/chat → forwards to OpenRouter, returns assistantMessage + optional boardUpdate
```

### Backend (`backend/app/`)

| File | Role |
|------|------|
| `main.py` | FastAPI app, all routes, auth middleware |
| `db.py` | SQLite init (`users` + `boards` tables), serialization helpers |
| `kanban_repo.py` | Read/write board JSON for a user |
| `ai_client.py` | HTTP client for OpenRouter |
| `ai_chat_models.py` | Pydantic models for AI request/response |

Auth is in-memory (`active_sessions` set); sessions survive until process restart.

### Frontend (`frontend/src/`)

`KanbanBoard.tsx` owns all board state and the dnd-kit drag context. It passes data down to `KanbanColumn` → `KanbanCard`. The `ChatSidebar` component lives alongside the board and sends messages to `/api/ai/chat`; if the response includes a `boardUpdate`, the board state is replaced.

Board saves are optimistic: local state updates immediately, then a 250 ms debounced `PUT /api/board` is fired.

`src/lib/kanban.ts` defines the `BoardData` type and pure board-manipulation logic. `src/lib/boardApi.ts` handles all HTTP calls.

### Data shape

```typescript
BoardData = {
  columns: { id: string, title: string, cardIds: string[] }[],
  cards: Record<string, { id: string, title: string, details: string }>
}
```

This blob is stored as `board_json` in SQLite's `boards` table (one row per user).

### AI structured output

The AI must return strict JSON matching the schema in `docs/ai-structured-output-schema.md`:
```json
{ "assistantMessage": "string", "boardUpdate": <optional full BoardData> }
```
A `boardUpdate` replaces the entire board; the backend validates the schema before applying it.

## Key Docs

- `docs/PLAN.md` — phased delivery plan (10 parts), design decisions, and trade-offs
- `docs/database-schema.md` — SQLite schema detail
- `docs/ai-structured-output-schema.md` — strict JSON schema for AI responses
- `AGENTS.md` — business requirements, limitations, coding standards, color scheme
- `backend/AGENTS.md` — backend scope and endpoint list
- `frontend/AGENTS.md` — frontend stack and component responsibilities

## Coding Standards (from AGENTS.md)

- Use latest library versions and idiomatic patterns
- Never over-engineer; always simplify; no unnecessary defensive programming
- Minimal comments; no emojis
- When hitting a bug, find the root cause with evidence before fixing
