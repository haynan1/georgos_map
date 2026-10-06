# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex) working on Georgos Map. Humans: see
README.md, ARCHITECTURE.md and CONTRIBUTING.md — this file is their condensed, enforceable form.

## Product

Multi-tenant web app for agricultural machinery fleet management (pt-BR users, B2B).
Desktop-first, responsive. UI copy is Brazilian Portuguese; code, identifiers and code
comments are English.

## Commands

| Task | Command |
|---|---|
| Run everything (dev) | `docker compose up --build` |
| Backend tests | `docker compose run --rm api-test` |
| Backend lint/types | `cd backend && uv run ruff format . && uv run ruff check . && uv run mypy app tests` |
| New migration | `docker compose run --rm migrate alembic revision --autogenerate --rev-id <NNNN> -m "<msg>"` (only `migrate` holds owner credentials) |
| Frontend checks | `cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build` |
| Regenerate API types | `cd frontend && pnpm gen:api` (API must be running on :8000) |

Run the relevant checks before declaring work done. All must pass.

## Non-negotiable rules

1. **Tenant isolation.** Every business table has `organization_id`, gets
   `enable_tenant_isolation("<table>")` in its migration, and every query filters by
   `auth.organization.id`. Add a test proving company A cannot read company B's rows.
2. **Authorization.** Every business endpoint depends on
   `require(Permission.X)` from `app.modules.auth.dependencies`. Never check roles by name.
3. **Secrets.** Never hardcode credentials, tokens or keys — not even "dev defaults".
   Configuration goes through `app/core/config.py` (env vars only).
4. **Errors.** Raise `AppError` subclasses from `app/core/errors.py`; never return ad-hoc
   error JSON. Messages are pt-BR, codes are stable snake_case English.
5. **Never log or echo secrets**: passwords, session tokens, invitation tokens, query strings.
6. **Migrations** are reviewed by hand after autogenerate and must pass
   `alembic upgrade head && alembic check && alembic downgrade base && alembic upgrade head`.
7. **Frontend data** goes through the typed `api` client (`@/lib/api/client`), never raw
   `fetch`. Never store tokens in localStorage/sessionStorage.
8. **shadcn CLI caveat:** after `shadcn add`, ensure imports use `@/lib/utils`, never the npm
   package `cn`; remove `cn` from package.json if the CLI added it.
9. **No new dependency** without a one-line justification in the PR description.
10. **Tests ship with the change.** Backend tests run against real PostgreSQL as the
    least-privileged runtime role (see `backend/tests/conftest.py`).

## Layout

- `backend/app/modules/<domain>/` — `models.py`, `schemas.py`, `service.py` (no HTTP),
  `router.py` (thin). Register models in `app/db/registry.py`, routers in `app/main.py`.
- `frontend/src/routes/_app/` — authenticated pages; `src/features/<domain>/` — logic;
  `src/components/ui/` — shadcn primitives; design tokens in `src/styles/globals.css`.

## Design bar

Dark-first, editorial typography (Instrument Serif for display, Geist for UI, Geist Mono for
data), one accent color (signal lime) reserved for primary actions, focus and live state.
Accessible by default: visible labels, errors next to fields, keyboard navigation, visible
focus, `prefers-reduced-motion` respected, 44px touch targets on mobile.
