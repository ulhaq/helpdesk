# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

**Helpdesk** - a multi-tenant customer support SaaS for small teams, built on a B2B SaaS platform: auth, organizations, RBAC, Stripe billing with plan limits, audit log, GDPR tooling, email + in-app notifications, and a bilingual (da/en) prerendered marketing site.

Product-specific code lives in one package per side - `backend/src/helpdesk/` and `frontend/src/helpdesk/`:
- **Tickets & contacts** - org-scoped shared inbox (per-organization numbers, status, priority, assignment, public replies, internal notes); contacts are customers without platform accounts, matched by email.
- **Support widget** - `frontend/public/widget.js` embeds `/widget/<slug>` in an iframe on any website; backed by the public `/v1/widget/<slug>` API and signed contact tokens.
- **Knowledge base & help center** - Markdown articles (rendered server-side with raw HTML disabled) managed at `/knowledge-base`, published at `/help/<slug>` and searchable from the widget.
- **Reports** - `/reports` (volume, backlog, response/resolution times, workload).
- **Worker loop** - auto-closes tickets left resolved (`HELPDESK_AUTO_CLOSE_RESOLVED_AFTER_DAYS`).

Product identity (name, domains, support email, legal entity) is in `frontend/src/brand.ts` and `APP_NAME` / `EMAIL_FROM_*` in `backend/.env`. Plan copy lives in the product locales (`planComparisonRows` / `planDescriptions`); product plan limits (`tickets_per_month`, `kb_articles`) are seeded by the helpdesk migration.

## Repository Structure

Full-stack multi-tenant SaaS:
- `backend/` - FastAPI + Python, PostgreSQL, async SQLAlchemy, Alembic migrations. See `backend/CLAUDE.md`.
- `frontend/` - Vue 3 + TypeScript, Vite, Pinia, file-based routing. See `frontend/CLAUDE.md`.

Both sides are split into a generic SaaS **platform** package and the
**product** package (`src/platform/` + `src/helpdesk/`), wired together by a thin
assembly layer (`bootstrap.py` / `main.ts`). The platform never imports product
code - enforced by import-linter (backend) and ESLint (frontend). To build a
different product on the platform, see `docs/adding-a-domain-module.md`.

## Running Locally

**Recommended: Docker Compose** (runs postgres, mailhog, backend, worker, and frontend together):

```bash
cp backend/.env.example backend/.env   # fill in secrets
make up-local                          # starts all services + pgadmin + mailhog
make up-local 1                        # port offset: adds 1 to every host port (for parallel git worktree stacks)
make down                              # stop everything
make logs                              # tail all logs
```

Services: backend API on `:8000`, frontend on `:5173`, pgadmin on `:5050`, mailhog UI on `:8025`.

**Without Docker** (run each in a separate terminal, `cd` first):

```bash
# Terminal 1 - backend API
cd backend && uv run poe dev

# Terminal 2 - background worker (ticket auto-close, GDPR retention, billing cleanup)
cd backend && uv run python worker.py

# Terminal 3 - frontend
cd frontend && npm run dev
```

The frontend dev server proxies `/v1` → `localhost:8000`.

## Two-Process Backend Architecture

The backend runs as **two separate processes**:

| Process | Entry point | What it does |
|---------|-------------|--------------|
| **API** | `src/main.py` (uvicorn) | Handles HTTP requests |
| **Worker** | `worker.py` | Runs the helpdesk auto-close loop, GDPR retention, billing cleanup, and trial reminder loops as concurrent asyncio tasks |

Adding a new background loop: implement a `run_X_loop(session_factory)` coroutine and register it as a task in `worker.py`. Never start background tasks inside `main.py`'s lifespan - horizontal API scaling would cause duplicate runs.

## Permission Flow (Backend → Frontend)

Platform permissions are a `Permission` StrEnum in `backend/src/platform/enums.py`; product permissions are `HelpdeskPermission` in `backend/src/helpdesk/enums.py`. The composition root (`backend/src/bootstrap.py`) merges both into the seeded `DEFAULT_ROLES`. At login, the API returns the user's flattened permission list; the frontend stores it in the profile store and checks it via `hasPermission()` / `usePermission()` / `<PermissionGuard>`.

When adding a new permission-gated feature:
1. Add the enum value: platform features in `backend/src/platform/enums.py`, product features in `backend/src/helpdesk/enums.py` (append - permission ids follow enum order)
2. Add a human-readable description to the `PERMISSION_DESCRIPTIONS` / `HELPDESK_PERMISSION_DESCRIPTIONS` map in the same file
3. Assign it to the appropriate default roles (`DEFAULT_ROLES` / `HELPDESK_DEFAULT_ROLE_PERMISSIONS`)
4. Guard the backend route with `require_permission(Permission.X)`
5. Guard frontend UI with `<PermissionGuard permission="x:y">` or `hasPermission('x:y')`, the page with `meta.permission`, and nav items with `permission`

Tests hardcode permission counts and ids (`tests/api/test_permission.py`, seeded Member role in `test_role.py` / `test_user.py`) - update them with the enum.

## Public (Customer-Facing) Surfaces

Customers never log in. The widget (`/v1/widget/<slug>`) and help center (`/v1/help/<slug>`) APIs are unauthenticated and rate limited; they resolve the organization from the support site slug and scope every repository to it. Widget access uses signed contact tokens (`backend/src/helpdesk/contact_token.py`): the token returned to the browser that submitted a ticket opens only that ticket, emailed links open all of the contact's conversations. On the frontend these pages use `meta: { layout: bare, public: true }` and the helpdesk `publicClient`, which never sends agent credentials; nginx lets any origin frame `/widget/*` only.

## Email / Notifications

Outbound email uses SMTP (mailhog in local dev).
Templates live in `backend/src/platform/templates/` (platform emails) and `backend/src/helpdesk/templates/` (product emails, registered in `bootstrap()`), written in MJML under `emails/mjml/<locale>/` and committed compiled to `emails/<locale>/*.html`. Email is sent after the response via `BackgroundTasks` (API) or `asyncio.to_thread(send_email, ...)` (worker) so SMTP calls don't block the event loop. In-app notifications are written to the `notification` table; the frontend renders product notification types through presenters in `frontend/src/helpdesk/notifications/`.
