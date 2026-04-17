# Code Review: Full-Stack Kanban + AI Chat App

_Reviewed: 2026-04-17_

---

## 1. Code Correctness & Bugs

### Critical Issues

None found. Core logic is sound with proper validation.

### Minor Issues

- **Possible race condition in session cleanup** (`main.py` ~line 138)
  Sessions are cleaned up lazily when accessed; expired sessions accumulate in memory until touched. Low impact for single-user MVP, but could grow unbounded in long-running containers.

- **Missing board state fallback** (`kanban_repo.py` line 36)
  Returns `{}` when board row is missing after `ensure_user_board()`. The frontend expects `{columns: [...], cards: {...}}`. Should return `default_board()` instead.

- **Inconsistent error kind** (`ai_client.py` ~line 290)
  Upstream error falls through to generic handler that returns `kind="upstream"`, but context suggests it should be `"upstream_error"` for consistency. Still returns 502; low impact.

---

## 2. Security

### Authentication

- Hardcoded credentials with env override acceptable for documented MVP scope.
- In-memory `active_sessions` dict loses all sessions on restart; acceptable for single-container.
- Session TTL 8 hours: reasonable.
- Cookie flags: `httponly=True`, `samesite="lax"`, `secure` tied to `ENVIRONMENT=production`. Correct.

### Input Validation

- Pydantic models enforce board shape, card ID uniqueness, and field lengths. Strong.
- AI response validated against schema before applying; returns 502 on failure.
- Chat history capped at 50 turns, content capped at 4000 chars.

### Injection & XSS

- Parameterized SQLite queries throughout — no SQL injection risk.
- Login page error flag is boolean; no user input echoed into HTML.
- No `eval()` or `innerHTML` in frontend.

### CORS

- `allow_origins=[_frontend_url]` with configurable env var. Requires correct override in production.

### Path Traversal

- `FRONTEND_DIR / full_path` uses Python `Path` objects, which prevent `../` traversal. Safe.

---

## 3. Code Quality & Style

Project standards: no over-engineering, minimal comments, idiomatic patterns.

**Overall: strong adherence.**

- Clean separation across `main.py`, `db.py`, `kanban_repo.py`, `ai_client.py`.
- Frontend state management is appropriate for single-board scope (no unnecessary Redux/context).
- React hooks and dnd-kit used idiomatically.
- Type hints throughout backend.

### Minor Style Issues

- **Inconsistent error shape**: backend returns `{error: "...", message: "..."}` but frontend `parseApiError` defensively handles both `detail: string` and `detail: {message: string}`. Works but fragile — standardise the shape.
- **Comment in `kanban_repo.py` line 35**: "Defensive: should not happen" — contradicts project standards. Remove and handle cleanly.
- **Magic strings in `kanban.ts`** (`"card"`, `"chat"` ID prefixes): minor code smell; extracting to constants would be cleaner but not urgent.

---

## 4. Performance

- **Database**: single-user, no N+1 queries, `username` indexed, foreign keys on. Fine.
- **Board size**: no column/card count limit; entire blob loaded per request. Acceptable for typical use; would degrade at 1000+ cards.
- **Saves**: 250 ms debounce + optimistic update. Good UX.
- **AI timeout**: 15 s. Reasonable.
- **JSON parsing fallback** (`ai_client.py` lines 228–258): three sequential strategies (direct, code fence, substring). O(n) string ops, acceptable for typical LLM response sizes.
- **No pagination/virtualisation**: assumes <100 cards. Acceptable for MVP.

---

## 5. Test Coverage Gaps

### Backend

Covered: auth flows, board CRUD, model validation, AI error handling, structured output parsing.

Gaps:
- No test for **session expiration** (TTL check exists in code, not exercised in tests).
- No full `/api/ai/chat` **integration test** with a mock OpenRouter transport.
- No **AI timeout test** (mock slow transport).
- No test for **malformed `board_json`** in the database (`deserialize_board()` with invalid JSON).
- Limited `test_ai_client.py`: missing content-array parsing and code-fence edge cases.

### Frontend

Covered: card/column CRUD, drag-and-drop, board persistence, chat message flow, error states, board update application.

Gaps:
- No edge-case tests: very long card titles, empty board initial state.
- No **accessibility tests** (keyboard navigation, axe-core).
- No coverage enforcement in `package.json` (backend enforces 80%; frontend does not).

---

## 6. Architectural Concerns

### Strengths

- Clear HTTP / business-logic / data-access layering.
- Frontend API calls isolated in `boardApi.ts`; pure utilities in `kanban.ts`.
- Stateless API — all state in request body or DB.
- Structured AI output with validation.

### Concerns

- **Session storage**: `active_sessions` dict unsuitable for multi-instance deploy. Acknowledged limitation.
- **Board as full blob**: no delta/patch, no audit trail. Simple and acceptable for MVP; would need rethinking for multi-user.
- **AI integration fragility**: no retry on invalid AI JSON — user must re-send. Acceptable for MVP.
- **Frontend state ownership**: all state in `KanbanBoard.tsx`, props drilled down. Fine for single board; would need context/provider pattern for multi-board.

---

## 7. Issues by Severity

| Severity | Issue | Location | Recommended Fix |
|----------|-------|----------|-----------------|
| Medium | Empty dict fallback instead of default board | `kanban_repo.py:36` | Return `default_board()` |
| Low | Session cleanup unbounded | `main.py` sessions dict | Add periodic cleanup |
| Low | Inconsistent error kind string | `ai_client.py:290` | Rename to `"upstream_error"` |
| Low | Defensive comment violates project standards | `kanban_repo.py:35` | Remove comment |
| Low | Missing AI integration test | `backend/tests/` | Add `/api/ai/chat` mock test |
| Low | Missing session expiration test | `backend/tests/` | Add TTL expiry test |
| Low | No frontend coverage enforcement | `frontend/package.json` | Add Vitest coverage threshold |

---

## 8. Recommendations

**High priority**
1. Fix `kanban_repo.py:36` — return `default_board()` not `{}`.
2. Add integration test for `/api/ai/chat` with mock transport.
3. Add session expiration test.

**Medium priority**
4. Standardise error response shape across backend and frontend.
5. Add edge-case tests: empty board, long card titles.
6. Add bounded session cleanup (e.g., trim on login or background task).

**Low priority**
7. Add frontend Vitest coverage threshold.
8. Add accessibility tests (axe-core).
9. Extract ID prefix strings to constants in `kanban.ts`.

---

## Overall Assessment

The codebase is clean, well-structured, and appropriate for its stated MVP scope. Security is sound. Code follows project standards well. The main gaps are in test coverage (AI integration, edge cases, expiry paths) rather than in correctness or architecture.
