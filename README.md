# Helpdesk

A multi-tenant helpdesk for small support teams, built on a production-ready B2B SaaS platform: FastAPI + PostgreSQL backend, background worker, and a Vue 3 frontend with a prerendered bilingual marketing site.

The product code lives in one package per side (`backend/src/helpdesk/`, `frontend/src/helpdesk/`); everything else is the reusable platform it plugs into.

## Features

**Helpdesk**

- **Shared inbox**: org-scoped tickets with per-organization numbers, status (open / waiting on customer / resolved / closed), priority, assignment, public replies and internal notes
- **Contacts**: customers without platform accounts, matched by email
- **Embeddable support widget**: one `<script>` tag on any website opens an iframe where customers start conversations, follow them and reply
- **Knowledge base & public help center**: Markdown articles in categories, a searchable help center per organization at `/help/<slug>`, and article search inside the widget
- **Reports**: ticket volume, backlog, first-response and resolution times, breakdowns and agent workload
- **Automation**: tickets left resolved are closed by a worker loop; agents are notified in-app about assignments and customer activity; customers get localized emails with a secure conversation link

**Platform**

- **Multi-tenant** organisations with enforced tenant isolation and fine-grained RBAC (roles, permissions, API tokens)
- **Auth**: JWT access tokens + httponly refresh cookies, email verification, password reset, invites, multiple organisations per user
- **Billing** via Stripe: plans, trials, checkout, customer portal, webhooks, plan features, seat/usage/capacity limits (tickets per month, knowledge base articles)
- **Audit log, GDPR export/erasure/retention**, cookie consent
- **Notifications**: localized transactional email (Danish/English, MJML templates) and in-app notifications
- **Marketing site**: localized routes (`/da/...`, `/en/...`), SSG prerendering, SEO tags, generated sitemap/robots, contact form, waitlist mode

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.14, FastAPI, async SQLAlchemy, PostgreSQL, Alembic, `uv` |
| Worker | Standalone asyncio process (ticket auto-close, GDPR retention, billing cleanup, trial reminders) |
| Frontend | Vue 3, TypeScript, Vite + vite-ssg, Pinia, vue-i18n, Tailwind + Reka UI, file-based routing |
| Infra | Docker Compose (postgres, pgadmin, mailhog, umami, backend, worker, frontend) |

## Architecture

Both sides of the codebase are split into a generic, reusable **SaaS platform** and the **product domain**, wired together by a thin assembly layer. The platform never imports product code - enforced in CI by [import-linter](https://import-linter.readthedocs.io) on the backend and an ESLint `no-restricted-imports` rule on the frontend.

```
backend/src/                          frontend/src/
├── platform/   generic SaaS core     ├── platform/   generic app shell
│   ├── core/   config, db, security  │   ├── pages/ components/ stores/
│   ├── models/ repositories/         │   ├── api/ composables/ layouts/
│   ├── services/ routers/ schemas/   │   ├── locales/ types/
│   ├── billing/ templates/           │   ├── config.ts    (homeRoute)
│   └── enums.py                      │   └── navigation.ts (nav registry)
├── helpdesk/   the product           ├── helpdesk/   the product
│   ├── models/ repositories/         │   ├── pages/ components/ stores/
│   ├── services/ routers/ schemas/   │   ├── api/ locales/ types/
│   ├── templates/ (MJML emails)      │   ├── notifications/ styles/
│   ├── hooks.py enums.py worker.py   │   └── index.ts  (module entry)
├── bootstrap.py  composition root    ├── brand.ts      product identity
├── main.py       API assembly        ├── main.ts       assembly
└── init_db.py    seeding             └── router/ plugins/ App.vue
                                      public/widget.js  embeddable loader
```

How the two halves connect without the platform knowing about the product:

- **Hooks** (backend): the platform emits lifecycle events (`MEMBER_ADDED`, `MEMBER_REMOVED`, `PLAN_CHANGED`); the product registers async handlers in `bootstrap()` (e.g. a removed member's tickets return to the queue).
- **Composition registry** (backend): `bootstrap.py` merges platform + product permissions, roles, email subjects, and template directories at startup.
- **Registries** (frontend): the product registers sidebar nav items (optionally permission-gated), notification presenters, and the authenticated home route from `src/helpdesk/index.ts` / `main.ts`; locale trees are deep-merged in the i18n plugin.

### Public, customer-facing surfaces

| Surface | Frontend | API | Access |
|---------|----------|-----|--------|
| Support widget | `/widget/<slug>` (iframe, loaded by `public/widget.js`) | `/v1/widget/<slug>/...` | Signed contact tokens; rate limited |
| Help center | `/help/<slug>` | `/v1/help/<slug>/...` | Published articles only; rate limited |

The token handed to a browser that just submitted a ticket opens that ticket only; links sent by email open all of the contact's conversations. Public pages use the `bare` layout with `meta.public`, which skips the host redirect and never touches an agent session. nginx allows any origin to frame `/widget/*` and nothing else.

Embed the widget with:

```html
<script src="https://app.example.com/widget.js" data-site="your-support-address" async></script>
```

### Two-process backend

| Process | Entry point | Role |
|---------|-------------|------|
| API | `src/main.py` (uvicorn) | HTTP requests |
| Worker | `worker.py` | Ticket auto-close, GDPR retention, billing cleanup, trial reminders |

Background loops live only in the worker so the API can scale horizontally without duplicate job runs or duplicate emails.

## Making it your own

1. **Brand**: edit `frontend/src/brand.ts` (name, domains, support email, legal entity) and set `APP_NAME` / `EMAIL_FROM_NAME` in `backend/.env`. Replace `frontend/public/{favicon.svg,logo.png,og-image.png}`.
2. **Plans**: adjust the seeded plans/prices/seat limits in the initial migration, the helpdesk limits (`tickets_per_month`, `kb_articles`) in the helpdesk migration, and the plan copy (`planComparisonRows`, `planDescriptions`) in the product locales.
3. **Legal**: adapt `frontend/src/platform/pages/terms.vue` and `privacy-policy.vue` (templates - get them reviewed).
4. **Deploy config**: `etc.nginx.sites-available.example`, `ANALYTICS_ORIGIN` in `docker-compose.yml`, the deploy path in `.github/workflows/ci.yml`.
5. **A different product**: the platform is product-agnostic - swap the `helpdesk` package for your own, step by step in [`docs/adding-a-domain-module.md`](docs/adding-a-domain-module.md).

Architecture details live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Getting Started

### Docker Compose (recommended)

```bash
cp backend/.env.example backend/.env   # fill in secrets (APP_SECRET, DB_*, ...)
make up-local                          # postgres, mailhog, pgadmin, backend, worker, frontend
make logs                              # tail everything
make down                              # stop
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API (+ OpenAPI docs) | http://localhost:8000 |
| Mailhog (caught email) | http://localhost:8025 |
| pgAdmin | http://localhost:5050 |

### Without Docker

Run each in its own terminal:

```bash
# 1 - backend API
cd backend && uv run poe dev

# 2 - background worker
cd backend && uv run python worker.py

# 3 - frontend (proxies /v1 -> localhost:8000)
cd frontend && npm run dev
```

Database setup and seeding (migrations + default roles/permissions/plans):

```bash
cd backend && python -m src.init_db
```

## Development

### Backend (`cd backend`, package manager: `uv`)

```bash
uv run poe dev      # dev server on :8000
uv run poe format   # ruff format + autofix
uv run poe lint     # ty (type check) + ruff + import-linter boundary contract
uv run poe test     # pytest (in-memory SQLite, no external services)
alembic revision --autogenerate -m "..."   # new migration
alembic upgrade head
```

Without a `backend/.env`, give the settings a parseable database URL for tests: `DB_CONNECTION=postgresql+psycopg://localhost/test uv run poe test`.

Email templates are written in MJML (`templates/emails/mjml/<locale>/`) and committed compiled: `cd templates/emails/mjml/en && mjml ticket-reply.mjml -o ../../en/ticket-reply.html`.

### Frontend (`cd frontend`)

```bash
npm run dev         # vite dev server on :5173
npm run typecheck   # vue-tsc
npm run lint        # eslint (includes the platform/product boundary rule)
npm run build       # production build (prerenders marketing pages, emits sitemap/robots)
npm run test:e2e    # playwright (needs the dev stack running)
```

Routes are file-based: adding a page under `src/platform/pages/` or `src/helpdesk/pages/` creates a route. Components in both `components/` roots are auto-registered.

### Key backend conventions

- **Layering**: routers → services → repositories → models; services raise `ClientException(ErrorCode.X)`, middleware renders consistent JSON errors.
- **Tenant isolation**: repositories extending `OrganizationScopedRepository` refuse unscoped queries unless `.unscoped` is used explicitly. Public endpoints scope themselves from the support site's slug.
- **Permissions**: `Permission` (platform) and `HelpdeskPermission` (product) StrEnums, merged and seeded by `bootstrap.py`; guard routes with `require_permission(...)` and frontend UI with `<PermissionGuard>` / `hasPermission()`.

### Key frontend conventions

- **Stores are the data gateway**: components never import `api/*` modules directly; every read/write goes through a Pinia store action. Customer-facing stores use a separate public API client that never sends agent credentials.
- **i18n everywhere**: all user-facing strings come from `vue-i18n` (`da` default, `en`), platform and product locale trees merged at startup.

## Repository Layout

```
├── backend/         FastAPI API + worker (see backend/CLAUDE.md)
├── frontend/        Vue 3 SPA + marketing site (see frontend/CLAUDE.md)
├── docs/            adding-a-domain-module.md + operational runbooks
├── scripts/         db-init / db-backup / db-restore
├── docker-compose.yml (prod) / docker-compose.dev.yml (local dev, used by Makefile)
└── Makefile         up / up-local / down / logs / shell-backend / shell-worker
```
