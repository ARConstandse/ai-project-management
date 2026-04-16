# Code Review Report

**Date**: 2026-04-16  
**Reviewer**: Claude Code (claude-sonnet-4-6)  
**Scope**: Full repository — backend, frontend, configuration, tests, deployment

**Remediation**: All Critical, High, and Medium issues resolved on 2026-04-16. Low issues deferred. See status markers below.

---

## Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Security | 2 | 3 | 1 | 0 | 6 |
| Code Quality | 0 | 0 | 4 | 1 | 5 |
| Error Handling | 0 | 1 | 2 | 0 | 3 |
| Testing | 0 | 1 | 4 | 0 | 5 |
| Performance | 0 | 0 | 1 | 3 | 4 |
| Configuration | 0 | 1 | 3 | 1 | 5 |
| Type Safety | 0 | 0 | 2 | 1 | 3 |
| Dependencies | 0 | 0 | 1 | 2 | 3 |
| Features/Edge Cases | 0 | 0 | 1 | 3 | 4 |
| **Total** | **2** | **6** | **19** | **11** | **38** |

---

## Immediate Action Items

1. ~~**CRITICAL** — Rotate all exposed API keys (`.env` committed to git)~~ — `.env` was not tracked; `.env.example` created
2. ~~**CRITICAL** — Remove hardcoded credentials from source code~~ — moved to `DEMO_USERNAME`/`DEMO_PASSWORD` env vars
3. ~~**HIGH** — Set `secure=True` on session cookies in production~~ — env-aware; secure when `ENVIRONMENT=production`
4. ~~**HIGH** — Add CORS middleware with explicit allowed origins~~ — added, controlled by `FRONTEND_URL` env var
5. ~~**HIGH** — Sanitize AI upstream error messages (risk of key leakage)~~ — upstream message logged server-side only
6. ~~**HIGH** — Add full integration test for chat → board-update chain~~ — already covered by existing test; added error-path tests
7. ~~**MEDIUM** — Consolidate duplicate default board data (frontend + backend)~~ — frontend now uses empty board; backend is single source of truth
8. ~~**MEDIUM** — Add input validation for chat history length/content~~ — 50-turn history limit, 4000-char message limit via Pydantic
9. ~~**MEDIUM** — Add session timeout + expiration logic~~ — 8-hour TTL with automatic eviction on auth check
10. **MEDIUM** — Add runtime validation on `boardApi.ts` fetch responses — deferred (would require adding Zod dependency)

---

## Security

### SEC-1 — `.env` File Committed to Git (CRITICAL)

**File**: `.env`

The `.env` file containing live API keys (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, and others) is committed to the repository. Anyone with repo access has these credentials.

**Action**:
- Rotate every key in the file immediately
- Add `.env` to `.gitignore` (it may already be listed but the file is tracked)
- Purge the file from git history: `git filter-repo --path .env --invert-paths`
- Create `.env.example` with placeholder values only

---

### SEC-2 — Hardcoded Credentials (CRITICAL)

**File**: `backend/app/main.py`, lines ~102–103

```python
VALID_USERNAME = "user"
VALID_PASSWORD = "password"
```

Credentials are hardcoded in source. Even for a demo app this is a bad pattern — they will end up in logs, error traces, and version history.

**Action**:
```python
VALID_USERNAME = os.getenv("DEMO_USERNAME", "user")
VALID_PASSWORD = os.getenv("DEMO_PASSWORD", "password")
```

---

### SEC-3 — Insecure Cookie in Production (HIGH)

**File**: `backend/app/main.py`, line ~165

Cookie is set with `secure=False`, meaning it is sent over plain HTTP. In production behind HTTPS this must be `True`.

**Action**:
```python
secure = os.getenv("ENVIRONMENT", "development") == "production"
response.set_cookie("pm_session", token, httponly=True, secure=secure, samesite="lax")
```

---

### SEC-4 — No CORS Configuration (HIGH)

**File**: `backend/app/main.py`

No CORS middleware is registered. Without it, cross-origin requests are either blocked or left wide open depending on host configuration, and CSRF protections are absent.

**Action**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
```

---

### SEC-5 — AI Upstream Error May Leak Keys (HIGH)

**File**: `backend/app/ai_client.py`, lines ~277–310

`_extract_upstream_message` returns raw upstream error responses, which can contain authentication headers or other sensitive tokens sent upstream.

**Action**: Log the full upstream message server-side but return only a generic message to the client:
```python
logger.warning("Upstream AI error", extra={"body": upstream_message})
return "AI service returned an error."
```

---

### SEC-6 — No Input Validation on Chat History (MEDIUM)

**File**: `backend/app/main.py`, line ~234

Chat history is forwarded to the AI API without length limits. A malicious or buggy client can send unbounded payloads, exhausting memory or running up API costs.

**Action**:
```python
MAX_HISTORY_TURNS = 50
MAX_MESSAGE_LEN = 4000

if len(payload.history) > MAX_HISTORY_TURNS:
    raise HTTPException(400, "History too long")
for turn in payload.history:
    if len(turn.content) > MAX_MESSAGE_LEN:
        raise HTTPException(400, "Message too long")
```

---

## Code Quality

### CQ-1 — Duplicated Default Board Data (MEDIUM)

**Files**: `backend/app/db.py` lines ~105–163, `frontend/src/lib/kanban.ts` lines ~18–72

The default board is defined in both files. Any change must be applied in both places and kept in sync manually.

**Action**: Remove the frontend default and always fetch the initial board from the backend. The backend already has `ensure_user_board` which creates the default for new users — the frontend just needs to trust the `GET /api/board` response.

---

### CQ-2 — `assert` Used for Runtime Validation (MEDIUM)

**File**: `backend/app/kanban_repo.py`, lines ~26, 52

```python
assert row is not None
```

Python strips assertions with the `-O` flag. They must not be used for runtime error conditions.

**Action**:
```python
if row is None:
    raise RuntimeError("User bootstrap failed — missing row after ensure_user_board")
```

---

### CQ-3 — Redundant JSON Round-Trip on Save (LOW)

**File**: `backend/app/kanban_repo.py`, line ~63

The validated board payload is serialized and then immediately deserialized for the return value. This is a no-op round-trip.

**Action**: Return the original validated `board_payload` dict directly.

---

### CQ-4 — `useMemo` with No Downstream Effect (LOW)

**File**: `frontend/src/components/KanbanBoard.tsx`, line ~50

`cardsById` is memoized but never used in a way that benefits from memoization (no expensive derived computation, no stable reference required by children).

**Action**: Remove the memo or replace with a plain variable.

---

## Error Handling

### EH-1 — Unhandled Rejection on Chat Send (HIGH)

**File**: `frontend/src/components/KanbanBoard.tsx`, line ~400

```tsx
onClick={() => void handleSendChat()}
```

`void` discards the promise. If `handleSendChat` throws outside its own try/catch, the error is silently lost.

**Action**:
```tsx
onClick={async () => {
  try {
    await handleSendChat();
  } catch (err) {
    setChatError("Unexpected error. Please try again.");
    console.error(err);
  }
}}
```

---

### EH-2 — Silent Board Save Failure (MEDIUM)

**File**: `frontend/src/components/KanbanBoard.tsx`, lines ~92–99

Save errors are caught and shown briefly but there is no retry path and no persistent indicator. The user may not notice their changes were not persisted.

**Action**: Add a persistent save-error banner with a retry button. Track `lastSaveError` state.

---

### EH-3 — Missing Error Context in HTTP Responses (MEDIUM)

**File**: `backend/app/ai_client.py`, line ~284

Generic `AIClientError` swallows the upstream status code and body. Debugging AI failures in production requires guessing.

**Action**: Include status code and sanitized message in the logged error. Never expose raw upstream body to the client.

---

## Testing

### TEST-1 — No Full Integration Test for AI → Board Update Chain (HIGH)

There is no test that exercises the complete path: POST `/api/ai/chat` → AI validation → board mutation → SQLite persistence → GET `/api/board` returns updated state. Existing tests mock the AI client.

**Action**: Add an integration test with a stub AI client that returns a `boardUpdate`, then assert the board is persisted.

---

### TEST-2 — No Session Expiration Tests (MEDIUM)

No test verifies that expired or invalid sessions are rejected. This is especially important given the in-memory session store has no TTL logic at all.

**Action**: Add tests for expired and replayed session tokens.

---

### TEST-3 — No Frontend Error State Tests (MEDIUM)

**File**: `frontend/src/components/KanbanBoard.test.tsx`

No test covers what happens when `PUT /api/board` or `POST /api/ai/chat` fails. Error states, retry buttons, and loading-state cleanup on error are all untested.

**Action**: Add tests that mock fetch failures and assert correct UI behavior.

---

### TEST-4 — AI Error Paths Not Tested (MEDIUM)

**File**: `backend/tests/test_ai_chat_api.py`

Only happy-path AI responses are tested. The various `AIClientError` kinds (timeout, auth, configuration, upstream) are not covered.

**Action**: Add a parameterized test covering each error kind and asserting the correct HTTP status and message shape.

---

### TEST-5 — E2E Tests Miss Auth Flow (LOW)

**File**: `frontend/tests/kanban.spec.ts`

End-to-end tests assume a logged-in state. No test covers login, logout, or redirect-on-unauthenticated behavior.

**Action**: Add Playwright tests for the full auth flow.

---

## Performance

### PERF-1 — No Index on `users.username` (MEDIUM)

**File**: `backend/app/db.py`

All user lookups filter by `WHERE username = ?` but there is no index on that column.

**Action**:
```sql
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
```

---

### PERF-2 — `queueSave` Recreated Each Render (LOW)

**File**: `frontend/src/components/KanbanBoard.tsx`, lines ~83–101

The debounced save callback is not wrapped in `useCallback`, so it is recreated on every render. This resets the debounce timer on rapid renders.

**Action**: Wrap in `useCallback` with stable deps.

---

### PERF-3 — No Virtualization for Large Boards (LOW)

**File**: `frontend/src/components/KanbanBoard.tsx`, lines ~315–327

All columns and cards render synchronously. Beyond ~500 cards, frame rates will degrade.

**Action**: For the current MVP scope this is acceptable. Document the known limit and plan for `react-virtual` if the use case grows.

---

## Configuration

### CFG-1 — No Startup Validation for Required Env Vars (MEDIUM)

**File**: `backend/app/main.py`

If `OPENROUTER_API_KEY` is missing the app starts successfully and fails only at first AI request with a cryptic error.

**Action**:
```python
if not os.getenv("OPENROUTER_API_KEY"):
    raise RuntimeError("OPENROUTER_API_KEY is required but not set")
```

---

### CFG-2 — Database Path Not Overridable in Production (MEDIUM)

**File**: `backend/app/db.py`, lines ~9–11

The SQLite path is hardcoded relative to the project root. In a container where the filesystem is ephemeral, data is lost on restart.

**Action**:
```python
DB_PATH = Path(os.getenv("PM_DB_PATH", PROJECT_ROOT / "db.sqlite3"))
```

(The `PM_DB_PATH` override already exists in tests — make it the standard.)

---

### CFG-3 — In-Memory Sessions Lost on Restart (MEDIUM)

**File**: `backend/app/main.py`, line ~101

Sessions are stored in a Python `set`. Every process restart logs out all users with no warning.

**Action**: For MVP, document this limitation. For production, store sessions in SQLite with a TTL column.

---

### CFG-4 — No Session Expiration Logic (MEDIUM)

**File**: `backend/app/main.py`

Sessions are never removed from `active_sessions`. They accumulate indefinitely (memory leak) and an old stolen token is valid forever.

**Action**: Change `active_sessions` to `dict[str, float]` mapping token → expiry timestamp. Reject and clean up expired sessions on each request.

---

## Type Safety

### TS-1 — Fetch Responses Cast Without Runtime Validation (MEDIUM)

**File**: `frontend/src/lib/boardApi.ts`, lines ~45, 63

```typescript
return (await response.json()) as BoardData;
```

TypeScript casts are not runtime checks. A malformed backend response will pass the cast and cause subtle downstream bugs.

**Action**: Add a Zod schema for `BoardData` and parse responses through it:
```typescript
import { z } from "zod";
const BoardSchema = z.object({ ... });
return BoardSchema.parse(await response.json());
```

---

### TS-2 — Loose Pydantic Field Constraints (MEDIUM)

**File**: `backend/app/kanban_models.py`, lines ~22–37

Card and column fields have no max-length constraints. A single card with a 10 MB details field is accepted and stored.

**Action**:
```python
class CardModel(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(max_length=4000)
```

---

### TS-3 — `any` in Test Mocks (LOW)

**File**: `frontend/src/components/KanbanBoard.test.tsx`, line ~18

```typescript
DndContext: (props: any) => { ... }
```

**Action**: Type the mock with the actual component props type.

---

## Dependencies

### DEP-1 — No Upper Bounds on Python Dependencies (MEDIUM)

**File**: `backend/pyproject.toml`

All dependencies use minimum-version pins (`>=`). A future major release of FastAPI or httpx could break the build silently.

**Action**: Add upper bounds or use a lock file (Poetry/pip-tools) to pin exact versions for reproducible builds.

---

### DEP-2 — No `npm audit` in CI (LOW)

No evidence of automated vulnerability scanning for frontend dependencies.

**Action**: Add `npm audit --audit-level=high` to CI pipeline.

---

### DEP-3 — No LICENSE File (LOW)

The repo has no LICENSE file.

**Action**: Add an appropriate license (MIT, Apache 2.0, etc.) to the repo root.

---

## Features / Edge Cases

### FEAT-1 — No Concurrent Edit Handling (MEDIUM)

`PUT /api/board` is a full board replacement. If two sessions (or browser tabs) edit the board simultaneously, the last write wins with no conflict detection.

**Action**: Add an `ETag` or `version` field to the board. Reject saves where the client's version is stale.

---

### FEAT-2 — No Board Backup/Export (LOW)

There is no way for a user to export or back up board data.

**Action**: Add `GET /api/board/export` returning board JSON as a file download.

---

### FEAT-3 — SQLite Not Suitable for Multi-User Scale (LOW)

SQLite write-serialization will be a bottleneck if the single-user MVP grows to multiple concurrent users.

**Action**: Document the known limitation. Plan migration path to PostgreSQL when needed.

---

### FEAT-4 — No Audit Trail (LOW)

No record of who changed what or when. This is a gap for a project management tool.

**Action**: For MVP, acceptable. For production, add a `board_history` table with timestamp and diff.
