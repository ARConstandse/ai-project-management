# Backend overview

The backend is a FastAPI service for the Project Management MVP.

Current scope (Part 4):

- Serves the statically built frontend at `/` when present
- Falls back to scaffold page if frontend build is not present
- Enforces demo login for Kanban access:
  - `GET /login`
  - `POST /login` with `user` / `password`
  - `GET /logout`
- Exposes demo API routes:
  - `GET /api/health`
  - `GET /api/hello`
- Includes backend tests in `backend/tests/`

Next phases will add authentication, persistence, and AI endpoints.