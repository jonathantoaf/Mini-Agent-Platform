# CLAUDE.md - Mini Agent Platform

## Project Overview

Multi-tenant backend API for managing AI agents with configurable tools. Agents can be run through a mock LLM pipeline that supports multi-step tool calling, prompt injection guardrails, and execution history tracking.

**Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0 async (asyncpg), PostgreSQL 16, Alembic, Pydantic v2, dependency-injector, uv

## Architecture

### Layered Architecture

```
Router (FastAPI) → Service (business logic) → Repository (data access) → DB Model (SQLAlchemy)
```

- **Routers** (`api/routers/`): HTTP endpoints, Pydantic validation, DI via `Depends()` factory functions
- **Services** (`services/`): Business logic, orchestrates repositories
- **Repositories** (`repositories/`): SQLAlchemy queries, cursor-based pagination, tenant filtering
- **DB Models** (`db/models/`): SQLAlchemy ORM models with UUID PKs

### Dependency Injection

**Container** (`containers.py`): Manages DB engine lifecycle and session factory.

```python
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    db_engine = providers.Resource(init_engine, ...)      # created on startup, disposed on shutdown
    session_factory = providers.Singleton(async_sessionmaker, bind=db_engine, ...)
```

**Per-request session** (`db/session.py`): Injected via `@inject` + `Provide[Container.session_factory]`, yields an `AsyncSession` with commit/rollback lifecycle.

**Router DI**: Per-request services use `Depends()` factories that receive the session:

```python
def get_tool_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ToolService:
    return ToolService(ToolRepository(session))

def get_agent_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentService:
    return AgentService(AgentRepository(session), ToolRepository(session))
```

**DI factory functions** live in `api/dependencies.py` — each creates a service with the required repositories from a shared session.

**Wiring**: All modules using `@inject` must be listed in `container.wire()` in `server.py`.

### Multi-Tenancy

- Auth via `X-API-Key` header → tenant_id lookup (`auth/api_key.py`), API keys parsed once at startup and cached
- `TenantId` type alias for route dependencies
- All DB queries filtered by `tenant_id` at repository layer
- **PostgreSQL RLS** as a database-level safety net (agents, tools, executions tables)

### Row-Level Security (RLS)

Two-layer tenant isolation:
1. **Application layer**: Repository queries filter by `tenant_id`
2. **Database layer**: RLS policies on `agents`, `tools`, `executions` tables

**How it works:**
- `get_session()` in `dependencies.py` calls `set_config('app.current_tenant_id', tenant_id, true)` per request
- RLS policies compare `tenant_id` column against `current_setting('app.current_tenant_id')`
- `agent_tools` junction table: no RLS — FK integrity to RLS-protected parents provides equivalent protection

**Two DB roles:**
- `postgres` (superuser): Used by Alembic for DDL migrations only (`DATABASE_MIGRATION_URL`)
- `app_user` (non-superuser): Used by the app at runtime (`DATABASE_URL`). RLS policies apply to this role. Superusers always bypass RLS, so the app must connect as a regular user.

**Alembic caveat:** Future DML migrations must either `SET LOCAL app.current_tenant_id` or temporarily disable RLS, since `app_user` is subject to RLS and `postgres` (used by Alembic) bypasses it.

### Key Patterns

- **Pydantic models** extend `SharedBaseModel` from `data_models/base.py` (auto camelCase serialization)
- **Cursor-based pagination** via `data_models/pagination.py` (encode_cursor/decode_cursor + PaginatedResponse[T]); defaults configured in settings. Invalid cursors raise `InvalidCursorError` → 400 Bad Request
- **Configurable defaults** — all runtime defaults (pagination limits, etc.) come from `settings.py` via `get_settings()`, never hardcoded
- **Settings** via `get_settings()` cached singleton (pydantic-settings with .env)
- **Async DB sessions** via `db/session.py` (get_async_session dependency)
- **Domain exceptions** in `exceptions/` package — naming convention: `<Entity>NotFoundError`, `<Entity>AlreadyExistsError`, plus `InvalidCursorError`, `PromptInjectionError`, `MaxIterationsError`, `InvalidModelError`, `ToolNotAssignedError`. Caught by routers and converted to HTTP errors.
- **Error handling** — routers catch domain exceptions and map to HTTP codes (400, 404, 409). Unhandled exceptions are caught by the global `exception_handler` in `server.py`, which logs the error and returns `{"detail": "Internal server error."}` with 500 status. All error responses use consistent JSON format `{"detail": "..."}`.
- **Uniqueness enforcement** via DB constraints + `IntegrityError` catch in services (no app-level check-then-act — avoids TOCTOU races)
- **Many-to-many relationships** — Agents ↔ Tools via `agent_tools` join table with CASCADE deletes. Agent model uses `lazy="selectin"` for eager loading. List queries use `result.unique().scalars()` to deduplicate rows from joins.

## Development Workflows

```sh
# Start PostgreSQL
docker-compose up -d postgres

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the server (port 5000)
uv run python main.py

# Run all checks (format, lint, typecheck, test)
uv run poe check

# Individual commands
uv run poe format      # Format code with ruff
uv run poe lint        # Lint code with ruff (with auto-fix)
uv run poe typecheck   # Type check with ty
uv run poe test        # Run tests with pytest
uv run poe check-fast  # Checks without tests

# Generate new migration
uv run alembic revision --autogenerate -m "description"
```

### CI/CD

GitHub Actions workflow in `.github/workflows/ci.yml` runs on push to `main` and all PRs.

- **`check`** — PostgreSQL 16 service container + `uv run alembic upgrade head` + `uv run poe check`
- **`build`** — Verifies Docker image builds (no push), uses GHA cache for layers

## Code Standards

- Type hints for all function parameters and return values
- `snake_case` for variables and functions, `PascalCase` for classes
- Line length: 100 characters
- Ruff for formatting and linting
- All new DB models must be imported in `db/models/__init__.py` for Alembic autogenerate

## Creating New Components

### New DB Model
1. Create in `db/models/new_model.py`
2. Import in `db/models/__init__.py`
3. Run `uv run alembic revision --autogenerate -m "add new_model table"`

### New Repository
1. Create in `repositories/new_repo.py`
2. Constructor takes `AsyncSession`
3. All queries filter by `tenant_id`

### New Service
1. Create in `services/new_service.py`
2. Define domain exceptions in `exceptions/__init__.py` using the convention `<Entity>NotFoundError`, `<Entity>AlreadyExistsError`

### New Router
1. Create in `api/routers/new_router.py`
2. Create DI factory function for service dependencies
3. Use `TenantId` dependency for tenant context
4. Register in `api/server.py`: `_app.include_router(router, prefix="/api/v1")`

### Pydantic Data Models
```python
from pydantic import Field
from agent_platform.data_models.base import SharedBaseModel

class MyModel(SharedBaseModel):
    my_field: str = Field(description="Description for API docs")
    another_field: int = Field(default=0, ge=0)
```

## Testing

- Tests in `tests/` directory mirror source structure
- `TestClient` from FastAPI for API/integration tests
- pytest fixtures in `conftest.py`
- Mock external dependencies with `pytest-mock`
- Two test API keys in test config for tenant isolation testing

## Exercise Requirements

This project implements a Mini Agent Platform with:
1. **Agent CRUD** — name, role, description, assigned tools. Filter by tool name.
2. **Tool CRUD** — name, description. Filter by agent name.
3. **Run Agent** — mock LLM with multi-step tool calling, prompt injection guardrails, loop safeguard
4. **Execution History** — paginated, includes tool call details
5. **Multi-Tenant Auth** — API key header, tenant_id column isolation, PostgreSQL RLS

### API Design
- All endpoints under `/api/v1/`
- Cursor-based pagination on all list endpoints
- 404 (not 403) for cross-tenant resource access attempts

## Project Structure

```
Mini-Agent-Platform/
├── agent_platform/
│   ├── api/
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── dependencies.py       # DI factory functions for services
│   │   ├── server.py             # App factory, middleware
│   │   └── static/               # Swagger/ReDoc assets
│   ├── auth/
│   │   └── api_key.py            # API key → tenant_id auth (cached at startup)
│   ├── data_models/
│   │   ├── agent.py              # Agent Create/Update/Response schemas
│   │   ├── base.py               # SharedBaseModel (camelCase)
│   │   ├── execution.py          # ExecutionResponse schema
│   │   ├── pagination.py         # Cursor-based pagination
│   │   ├── run.py                # RunRequest/Response, ChatMessage, ToolCallRecord
│   │   └── tool.py               # Tool Create/Update/Response schemas
│   ├── db/
│   │   ├── base.py               # SQLAlchemy Base
│   │   ├── models/               # ORM models (Agent, Tool, Execution)
│   │   └── session.py            # Async session factory
│   ├── repositories/             # Data access layer
│   ├── exceptions/               # Domain exceptions
│   ├── services/
│   │   ├── run/                  # Agent execution pipeline
│   │   │   ├── guardrail.py      # Prompt injection detection
│   │   │   ├── mock_llm.py       # Mock LLM adapter
│   │   │   ├── mock_tool_executor.py
│   │   │   ├── prompt_builder.py # Structured prompt construction
│   │   │   └── run_service.py    # Agentic loop orchestrator
│   │   ├── agent_service.py      # Agent CRUD + tool assignment
│   │   ├── execution_service.py  # Execution history retrieval
│   │   └── tool_service.py       # Tool CRUD
│   ├── containers.py             # DI container (DB engine, session factory)
│   └── settings.py               # Pydantic BaseSettings
├── alembic/                      # Database migrations
├── tests/                        # Mirrors source structure
├── docker-compose.yml            # PostgreSQL + app
├── Dockerfile                    # Multi-stage build
└── pyproject.toml                # Dependencies & tooling
```

## Environment Variables

```
DATABASE_URL=postgresql+asyncpg://app_user:app_user@localhost:5432/agent_platform
DATABASE_MIGRATION_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_platform
API_KEYS={"sk-tenant1-secret": "tenant_1", "sk-tenant2-secret": "tenant_2"}
APP_NAME=agent-platform
DEBUG=false
LOG_LEVEL=INFO
PAGINATION_DEFAULT_LIMIT=20
PAGINATION_MAX_LIMIT=100
RUN_MAX_ITERATIONS=10
ALLOWED_MODELS=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "claude-sonnet-4-5-20250514", "claude-haiku-4-5-20251001", "gemini-2.5-flash", "gemini-2.5-pro"]
```
