# Frontend Codebase Guide

## Purpose

The `frontend/` app is the current Kanban MVP UI. It is a Next.js app (App Router) with client-side state and drag-and-drop interactions. Today it is a standalone frontend demo and does not yet persist data to backend APIs.

## Stack

- Next.js `16.1.6`
- React `19.2.3`
- TypeScript
- Tailwind CSS v4 (via `@import "tailwindcss"`)
- `@dnd-kit` for drag-and-drop
- Vitest + Testing Library for unit tests
- Playwright for end-to-end tests

## Run and test

- Install: `npm install`
- Dev server: `npm run dev`
- Build: `npm run build`
- Unit tests: `npm run test:unit`
- E2E tests: `npm run test:e2e`
- All tests: `npm run test:all`

## Current architecture

- `src/app/page.tsx`
  - Renders `KanbanBoard` as the home page.
- `src/components/KanbanBoard.tsx`
  - Owns in-memory board state (`columns` + `cards`).
  - Handles drag start/end, column renaming, card create/delete.
  - Renders five Kanban columns and drag overlay.
- `src/components/KanbanColumn.tsx`
  - Column shell with editable title, droppable region, card list, and new-card form.
- `src/components/KanbanCard.tsx`
  - Sortable draggable card UI and delete action.
- `src/components/NewCardForm.tsx`
  - Expandable add-card form.
- `src/lib/kanban.ts`
  - Core board types, initial seed data, move algorithm, and ID helper.

## Styling and theme

- Global theme variables are defined in `src/app/globals.css`.
- Color variables match root project requirements:
  - `--accent-yellow: #ecad0a`
  - `--primary-blue: #209dd7`
  - `--secondary-purple: #753991`
  - `--navy-dark: #032147`
  - `--gray-text: #888888`
- Display/body fonts come from `next/font/google` in `src/app/layout.tsx`.

## Testing setup

- Unit tests:
  - `src/lib/kanban.test.ts` tests card movement logic.
  - `src/components/KanbanBoard.test.tsx` tests render, rename, add, and delete behavior.
- E2E tests:
  - `tests/kanban.spec.ts` covers board load, add card flow, and drag between columns.
- Vitest config:
  - `vitest.config.ts` uses `jsdom`, Testing Library setup, and V8 coverage reporter.

## Current limitations

- No authentication.
- No backend integration.
- No persistent storage.
- No AI chat sidebar.

## Notes for future phases

- Keep existing component boundaries where possible.
- Prefer extending `src/lib/kanban.ts` logic with tests before UI-level changes.
- Preserve `data-testid` usage because existing tests depend on it.
