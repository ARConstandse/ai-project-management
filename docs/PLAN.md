# Project Delivery Plan

This document is the execution checklist for building the MVP in phases.

## Global constraints (apply to all parts)

- [ ] Keep implementation simple; no extra features beyond MVP scope.
- [ ] Target about 80% unit test coverage when sensible, but prioritize high-value tests over coverage percentage.
- [ ] Add robust integration testing for each behavior introduced in a part.
- [ ] Use server-side login session/cookie behavior for auth-gated routes.
- [ ] Use SQLite and persist board state as JSON for MVP.
- [ ] Use OpenRouter model `qwen/qwen3.6-plus-preview:free` unless explicitly changed by user.
- [ ] For AI Structured Outputs, define and document strict schemas before implementation.

## Part 1: Plan and documentation baseline

### Checklist

- [x] Expand this plan with detailed implementation steps, tests, and success criteria for all parts.
- [x] Create `frontend/AGENTS.md` documenting current frontend architecture and testing setup.
- [x] Get user review and explicit approval before starting Part 2.

### Tests

- [x] Documentation review pass: all parts include checklists, tests, and success criteria.
- [x] User confirmation captured before coding begins.

### Success criteria

- [x] `docs/PLAN.md` is actionable and phase-based.
- [x] `frontend/AGENTS.md` accurately reflects current frontend codebase.

## Part 2: Scaffolding (Docker + FastAPI + scripts)

### Checklist

- [x] Create `backend/` FastAPI app skeleton with health and demo API route.
- [x] Add Dockerfile and container setup using `uv`.
- [x] Add `docker-compose.yml` (or equivalent simple runner) for local run.
- [x] Add `scripts/` start and stop scripts for Windows, macOS, Linux.
- [x] Serve example static page from backend root `/`.
- [x] Confirm static page can call demo API endpoint.

### Tests

- [x] Backend unit tests for health and demo API handlers.
- [x] Integration test: container starts and serves `/` and API route.
- [x] Script smoke tests: start script launches app; stop script shuts it down.
- [x] Coverage review: meaningful backend tests are in place; coverage is healthy.

### Success criteria

- [x] Local container run works end-to-end.
- [x] Visiting `/` shows hello-world static page.
- [x] Static page successfully calls backend API route.

## Part 3: Add frontend into backend serving path

### Checklist

- [x] Build frontend for production static output.
- [x] Configure backend to serve built frontend at `/`.
- [x] Preserve existing Kanban UX from current demo.
- [x] Ensure Docker image includes both backend and built frontend assets.

### Tests

- [x] Frontend unit tests for board/core interactions.
- [x] Integration test: running container serves Kanban at `/`.
- [x] End-to-end test: board loads with expected columns/cards.
- [x] Coverage review: meaningful frontend tests are in place; coverage is healthy.

### Success criteria

- [x] App root renders demo Kanban board from integrated stack.
- [x] Tests pass in CI/local containerized flow.

## Part 4: Fake sign-in flow (server-side session)

### Checklist

- [x] Add login page/flow for credentials `user` / `password`.
- [x] Implement server-side session cookie management.
- [x] Protect Kanban route(s) so unauthenticated users are redirected to login.
- [x] Add logout endpoint/action that clears server-side session.

### Tests

- [x] Backend unit tests for login validation/session creation/session clear.
- [x] Integration tests for auth guard and redirect behavior.
- [x] End-to-end tests for login success, login failure, and logout.
- [x] Coverage review: auth-related tests cover core behavior with meaningful scenarios.

### Success criteria

- [x] Unauthenticated access cannot reach Kanban page.
- [x] Valid login reaches Kanban; logout returns user to login page.

## Part 5: Database model and sign-off

### Checklist
- [x] Propose SQLite schema supporting multiple users and one board per user (MVP behavior).
- [x] Store board payload as JSON in SQLite.
- [x] Document schema, migration/init behavior, and trade-offs in `docs/`.
- [x] Get user sign-off on schema before API implementation.

### Tests
- [x] Unit tests for data model serialization/deserialization and defaults.
- [x] Integration test: DB auto-creates when missing.
- [x] Coverage review: DB tests focus on high-value behavior and edge cases.

### Success criteria
- [x] Approved schema documented clearly.
- [x] DB bootstraps cleanly on first run.

### Design decisions recorded

- Persist board state in `boards.board_json` (single JSON document) to keep MVP schema simple.
- Keep one-board-per-user invariant via `UNIQUE(user_id)` in `boards`.
- Use app-level DB bootstrap (`CREATE TABLE IF NOT EXISTS`) and no migration framework during MVP.
- Keep detailed schema/trade-offs in `docs/database-schema.md`.

## Part 6: Backend Kanban APIs

### Checklist
- [x] Implement API routes to fetch and update board for authenticated user.
- [x] Add service/repository layer for board read/write in SQLite JSON.
- [x] Validate payload shape and return clear API errors.
- [x] Ensure DB file is created if absent.

### Tests
- [x] Backend unit tests for handlers, service logic, and validation.
- [x] Integration tests for authenticated board read/write lifecycle.
- [x] Negative-path tests for invalid payload and unauthorized requests.
- [x] Coverage review: backend API tests cover critical success and failure paths.

### Success criteria
- [x] Board API supports reliable persistence for signed-in user.
- [x] API behaves correctly for success and failure paths.

### Design decisions recorded

- Expose board persistence via `GET /api/board` and `PUT /api/board` for authenticated users.
- Use a repository layer (`kanban_repo`) to isolate SQLite read/write from route handlers.
- Validate board payload with strict model checks:
  - `cards` key must match `card.id`.
  - all `column.cardIds` must exist in `cards`.
- Return `401` for unauthorized board access and `422` for invalid board payloads.
- Support deterministic tests with `PM_DB_PATH` override for temporary DB files.

## Part 7: Frontend + Backend persistence wiring

### Checklist

- [x] Replace in-memory frontend board state with backend API fetch/save.
- [x] Keep drag/drop, add, edit, delete, rename flows working with persistence.
- [x] Add loading and error states that remain minimal and clear.
- [x] Ensure data refresh reflects latest saved board.

### Tests

- [x] Frontend unit tests for API client/state transitions.
- [x] Integration tests with mocked backend responses.
- [x] End-to-end tests verifying persisted changes survive page refresh.
- [x] Coverage review: frontend persistence tests cover critical user flows.

### Success criteria

- [x] Kanban changes persist across reloads for authenticated session.
- [x] Existing Kanban interactions remain smooth and correct.

### Design decisions recorded

- Keep local optimistic board updates, then persist asynchronously through `PUT /api/board`.
- Load board from backend on mount (`GET /api/board`), with local seed as fallback if load fails.
- Debounce save calls (~250ms) to reduce redundant requests during rapid edits.
- Show minimal persistence state in UI: loading, saving, saved, and error.
- Keep backend default board seed aligned with the original frontend board so first run UX is unchanged.

## Part 8: AI connectivity through OpenRouter

### User-approved implementation notes

- Endpoint will be auth-protected (requires valid session cookie).
- Endpoint is temporary and dev-facing for connectivity verification.
- Connectivity check must call real OpenRouter (no mocking for manual smoke test).
- Apply explicit upstream timeout and categorized error mapping.
- Manual real-key smoke test is approved during Part 8 execution.

### Checklist

- [x] Add backend AI client using `OPENROUTER_API_KEY`.
- [x] Call OpenRouter model `qwen/qwen3.6-plus-preview:free`.
- [x] Implement a simple connectivity endpoint/task for prompt `2+2`.
- [x] Add timeout and clear error mapping for failed upstream calls.

### Tests

- [x] Unit tests for AI client request building and response parsing.
- [x] Integration test with mocked OpenRouter response.
- [ ] Manual smoke test using real key: `2+2` returns valid response.
- [x] Coverage review: AI client tests cover request, response, and failure handling.

### Success criteria

- [ ] Backend can successfully call OpenRouter and return response.
- [x] Failures are observable and user-safe.

### Design decisions recorded

- Added secure temporary dev endpoint `POST /api/ai/dev-connectivity` that requires login session.
- Endpoint triggers a real OpenRouter call with fixed prompt `2+2` and returns prompt, response, model, and latency.
- OpenRouter client timeout is explicitly set to 15 seconds.
- Upstream failures are categorized into configuration, timeout, auth, rate-limit, model-unavailable, network, invalid-response, and generic upstream errors.
- Real-key smoke test currently fails due provider-side model availability for `qwen/qwen3.6-plus-preview:free` (OpenRouter returns 404 "No endpoints found").

## Part 9: Structured Outputs for chat + optional board update

### Checklist

- [x] Define strict structured output schema in docs before coding.
- [x] Include board JSON, user message, and conversation history in AI request.
- [x] Parse model response into:
  - user-facing response text
  - optional board update payload
- [x] Validate structured output before applying board changes.
- [x] Persist board update only when output is valid and authorized.

### Tests

- [x] Unit tests for schema validation and transformation logic.
- [x] Integration tests for:
  - response-only outputs
  - response + board update outputs
  - invalid schema outputs
- [x] Safety tests to ensure invalid/malformed output does not corrupt board.
- [x] Coverage review: structured-output tests cover schema validity and safety behavior.

### Success criteria

- [x] Backend consistently returns typed chat responses.
- [x] Optional AI-driven board updates are applied only when valid.

### Design decisions recorded

- Added strict schema documentation in `docs/ai-structured-output-schema.md` before implementation.
- Added typed backend request/response/output models in `backend/app/ai_chat_models.py`.
- Added secure endpoint `POST /api/ai/chat` that requires authenticated session.
- AI request context includes current board JSON, user message, and prior conversation turns.
- Endpoint only persists `boardUpdate` when output validates against strict schema and board consistency checks.
- Invalid/malformed AI outputs return safe `502 ai_invalid_response` and do not mutate persisted board.

## Part 10: Sidebar AI chat UX + live board refresh

### Checklist

- [x] Build sidebar chat UI integrated into Kanban page.
- [x] Send user prompts and conversation history to backend chat endpoint.
- [x] Render assistant responses in chat thread.
- [x] When AI output includes a board update, refresh board UI automatically.
- [x] Keep UX clean and aligned with project color/theme system.

### Tests

- [x] Frontend unit tests for chat component rendering and state transitions.
- [x] Integration tests for chat request/response and board refresh triggers.
- [x] End-to-end tests for full flow: prompt -> assistant reply -> optional board change.
- [x] Coverage review: chat UI tests cover key conversation and board-update flows.

### Success criteria

- [x] Sidebar chat works reliably for conversation and board updates.
- [x] Board updates from AI are reflected immediately in UI.

### Design decisions recorded

- Added a right-side `Board Chat` panel directly on the Kanban page to keep chat and board actions in one view.
- Added frontend API client support for `POST /api/ai/chat` with typed request/response payloads.
- Chat requests send prior conversation turns as history and send the current user message separately.
- On AI response:
  - append assistant text to chat thread,
  - if `boardUpdate` is present, replace in-memory board state immediately without extra reload.
- Chat error states are shown inline with minimal status text to preserve existing clean MVP UX.

## Execution policy

- Complete one part at a time.
- After each part:
  - run relevant tests,
  - review whether test coverage is sufficient for risk, without adding low-value tests only for percentage,
  - summarize outcomes and remaining risks,
  - get user approval before advancing to the next part.