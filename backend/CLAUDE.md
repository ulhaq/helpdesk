# FastAPI Backend Project Guide

This file provides comprehensive guidance for working with this FastAPI multi-tenant backend project.

## Project Overview

**SaaS boilerplate backend** - multi-tenant FastAPI service with auth, organizations, RBAC, Stripe billing, audit log, GDPR tooling, and email/in-app notifications. Product code lives in `src/helpdesk/`: tickets and contacts, the embeddable support widget, the knowledge base and public help center, and reports.

**Key Characteristics:**
- Multi-tenant architecture with enforced tenant isolation
- Fine-grained RBAC with granular permissions (platform `Permission` + product `HelpdeskPermission`)
- Async/await throughout using SQLAlchemy async drivers
- Pydantic V2 for schema validation
- Alembic for database migrations
- Comprehensive pytest suite with in-memory SQLite testing
- Type hints throughout (enforced via ty)
- Line length limit: 88 characters

### Helpdesk product modules

| Path | Purpose |
|------|---------|
| `src/helpdesk/enums.py` | `HelpdeskPermission`, `TicketStatus`/`TicketPriority`/`TicketChannel`, `ArticleStatus`, audit actions, notification types, usage metrics (`tickets_per_month`, `kb_articles`), error codes, permission descriptions |
| `src/helpdesk/models/` | `Contact`, `Ticket`, `TicketMessage` (org-scoped, soft-deletable), `KbCategory`/`KbArticle`, `SupportSite` (one per org: public slug, branding, widget/help center switches) |
| `src/helpdesk/repositories/` | Org-scoped repositories + `SupportSiteRepository` (looked up by slug), `AgentRepository` (members holding a permission), `HelpdeskRepositoryManager` |
| `src/helpdesk/services/ticket.py`, `contact.py` | Agent inbox: ticket numbering, status timestamps, assignment + notifications, replies/internal notes, reply emails with a conversation link |
| `src/helpdesk/services/widget.py` | Public widget API: submit tickets, list/read/reply with contact tokens, access-link emails |
| `src/helpdesk/services/kb.py`, `help_center.py` | Knowledge base management (slugs, publish, capacity limit) and the public read-only help center |
| `src/helpdesk/services/reports.py` | Report summary computed from one bounded, scoped query |
| `src/helpdesk/contact_token.py` | Signed contact tokens (ticket-scoped when unverified, contact-scoped when emailed) |
| `src/helpdesk/markdown.py` | Article rendering with raw HTML disabled |
| `src/helpdesk/hooks.py` | `MEMBER_REMOVED` → unassign the member's tickets |
| `src/helpdesk/worker.py` | `run_auto_close_loop` - closes tickets left resolved, recording `worker_run` rows |
| `src/helpdesk/config.py` | `HelpdeskSettings` (`env_prefix="helpdesk_"`: contact token lifetime, auto-close) |
| `src/helpdesk/templates/emails/` | MJML sources (`mjml/<locale>/`) + compiled HTML for `ticket-reply`, `ticket-received`, `ticket-access` |

---

## Architecture

### Platform core vs. product domain

The backend is split into a **generic SaaS platform** (auth, organizations, users,
RBAC, billing, audit, GDPR) and the **product domain**. The core never imports
domain code; the two are wired together in exactly one place:

| Piece | Path | Purpose |
|-------|------|---------|
| Hook registry | `src/platform/core/hooks.py` | Core emits `HookEvent`s (`MEMBER_ADDED`, `MEMBER_REMOVED`, `PLAN_CHANGED`); domain modules register async handlers |
| Platform enums | `src/platform/enums.py` | Core `Permission`, `AuditAction`, `ErrorCode`, `PlanFeature`, `UsageMetric`, `DEFAULT_ROLES` - no domain members allowed |
| Domain enums | `src/helpdesk/enums.py` | Product permissions, audit actions, error codes, usage metrics, plus per-role grant/description contributions |
| Domain hooks | `src/helpdesk/hooks.py` | Handlers for platform lifecycle events |
| Domain settings | `src/helpdesk/config.py` | Independent settings namespace extending the shared `EnvSettings` base |
| Composition root | `src/bootstrap.py` | Merges core+domain permissions/roles (`ALL_PERMISSIONS`, `PERMISSION_DESCRIPTIONS`, `DEFAULT_ROLES`) and registers domain hooks, email subjects, and template directories via `bootstrap()` |

`bootstrap()` is called at startup by `src/main.py` (API) and `worker.py` (worker).
Seeding code (Alembic initial migration, `src/init_db.py`, `tests/conftest.py`) must
import the composed sets from `src.bootstrap`, never from `src.platform.enums` directly.

The import-linter contract in `pyproject.toml` forbids `src.platform` from importing
`src.helpdesk` - keep it pointed at your product package if you replace it.

**Building a new product on this backend** - replace the domain and keep the core
(full guide: `docs/adding-a-domain-module.md`):
1. Replace `src/helpdesk/` with your package (enums, models, repositories, services, routers, hooks).
2. Update `src/bootstrap.py`, the router includes in `src/main.py`, the model import in `alembic/env.py`, the loop registration in `worker.py`, and the import-linter contract.
3. Replace the helpdesk migration (`alembic/versions/*_helpdesk_core.py`) and the helpdesk tests; update the seeded Member role permissions in `src/init_db.py`.

### Layered Architecture: Routers > Services > Repositories > Models

- `routers/` - FastAPI route handlers; validate HTTP input, delegate to services
- `services/` - Business logic; coordinate repositories, raise `ClientException` on failures
- `repositories/` - SQLAlchemy data access; handle filtering, pagination, soft deletes
- `models/` - SQLAlchemy ORM entities
- `schemas/` - Pydantic request/response models
- `src/platform/core/` - Cross-cutting concerns: config, security (JWT/passwords), DI dependencies, error handling, rate limiting, hooks

### Key patterns

**Generic base classes** - `ResourceService[T]` and `SQLResourceRepository[T]` provide standard CRUD behavior. Domain-specific classes extend these; avoid duplicating CRUD logic.

**Dependency injection** - `src/platform/core/dependencies.py` provides `authenticate()` and `require_permission(Permission.X)` FastAPI dependencies for auth/authz. `RepositoryManager` in `src/platform/repositories/repository_manager.py` is the DI container for platform repositories; product code depends on `HelpdeskRepositoryManager` (`src/helpdesk/repositories/manager.py`) instead.

**Error handling** - Raise `ClientException(ErrorCode.X)` from services; the middleware in `src/platform/core/middlewares.py` converts these to consistent JSON error responses. Error codes are defined in `src/platform/enums.py` (platform) and `src/helpdesk/enums.py` (product).

**Multi-tenancy** - Users and resources belong to an `Organization`. Organization isolation is enforced at the repository level via `organization_id` foreign keys. Repositories extending `OrganizationScopedRepository` are **loud by default**: generic queries raise `UnscopedQueryError` unless `set_organization_scope()` was called; intentional cross-tenant access (auth identity lookups, workers, webhook handlers) must use the explicit `.unscoped` accessor.

**Plan limits** - Plan settings (`billing_plan_setting`) hold per-plan limits keyed by metric (`seats`, `tickets_per_month`, `kb_articles`, ...). Use `BaseService._require_capacity(metric, org_id, current_count)` for "how many can exist" limits and `require_limit(metric)` / `track_usage()` for per-period usage counters; code paths without a signed-in user (public endpoints) call `require_within_limit(repos, org_id, metric)`.

**Permissions** - Fine-grained RBAC using the `Permission` enum (`src/platform/enums.py`) plus `HelpdeskPermission` (`src/helpdesk/enums.py`). Users have roles; roles have permissions. Use `require_permission()` on routes to enforce access.

**Public endpoints** - The widget (`/v1/widget/{slug}`) and help center (`/v1/help/{slug}`) routers have no platform authentication. Every route is rate limited (`@limiter.limit`, which needs a `request: Request` parameter), resolves the `SupportSite` by slug and scopes all repositories to its organization before touching data. Widget calls carry `X-Contact-Token`; always check the token's organization matches the site and, for ticket-scoped tokens, the ticket id. Never return a contact-scoped token to a browser that has not proven it owns the email address - those are only sent by email.

**Query features** - Repositories support dynamic filtering via `ComparisonOperator` (eq, lt, gte, contains, in, between, etc.), pagination (`page_number`, `page_size`), and sorting.

### Database migrations
Add columns/tables in models, then `alembic revision --autogenerate`.
Prefer adding to an existing staged migration file over creating a new one.
The initial migration holds the platform schema and seeds (permissions, plans, seat limits); product tables and product plan limits go in product migrations.

### Testing
- Tests use **SQLite in-memory** database; no external DB needed
- `tests/conftest.py` provides: async test client, pre-seeded organizations/users/roles/permissions, and per-test DB teardown
- `asyncio_mode = auto` (set in `pytest.ini`); all test functions can be `async`
- Without a `.env`, settings need a parseable database URL at import time: `DB_CONNECTION=postgresql+psycopg://localhost/test uv run poe test` (tests still use SQLite)
- Product emails are not mocked globally - patch `send_email` in the service module under test (e.g. `src.helpdesk.services.ticket.send_email`)
- Platform tests must not import product code - use a test-local enum where a metric/feature is needed


## Commands (`cd backend` first)

```bash
# Format code
uv run poe format

# Lint (ty + ruff + import-linter boundary contract)
uv run poe lint

# Run all tests
uv run poe test

# Run a single test
uv run pytest ./tests/api/test_auth.py::test_register_an_account -v

# Start dev server
uv run poe dev

# Database setup (runs migrations + seeds data)
python -m src.init_db

# Drop all tables
python -m src.init_db drop

# Database migrations
alembic revision --autogenerate -m "description"   # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback last migration
```

**Package manager:** `uv` (use `uv add`, `uv run`, etc.)
