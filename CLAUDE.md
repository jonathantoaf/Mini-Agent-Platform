# CLAUDE.md - Mini Agent Platform

## Project Overview

Multi-tenant backend API for managing AI agents with configurable tools. Agents can be run through a mock LLM pipeline that supports multi-step tool calling, prompt injection guardrails, and execution history tracking.

**Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0 async (asyncpg), PostgreSQL 16, Alembic, Pydantic v2, uv

## Architecture

### Layered Architecture

```
Router (FastAPI) → Service (business logic) → Repository (data access) → DB Model (SQLAlchemy)
```

- **Routers** (`api/routers/`): HTTP endpoints, Pydantic validation, DI via `Depends()`
- **Services** (`services/`): Business logic, orchestrates repositories
- **Repositories** (`repositories/`): SQLAlchemy queries, cursor-based pagination, tenant filtering
- **DB Models** (`db/models/`): SQLAlchemy ORM models with UUID PKs

### Multi-Tenancy

- Auth via `X-API-Key` header → tenant_id lookup (`auth/api_key.py`)
- `TenantId` type alias for route dependencies (mirrors `CurrentUserId` pattern)
- All DB queries filtered by `tenant_id` at repository layer
- PostgreSQL RLS as a database-level safety net

### Key Patterns

- **Pydantic models** extend `SharedBaseModel` from `data_models/base.py` (auto camelCase serialization)
- **Cursor-based pagination** via `data_models/pagination.py` (encode_cursor/decode_cursor + PaginatedResponse[T])
- **Settings** via `get_settings()` cached singleton (pydantic-settings with .env)
- **Async DB sessions** via `db/session.py` (get_async_session dependency)
- **Manual DI** via FastAPI `Depends()` factory functions in routers (no container auto-wiring for domain code)
- **Service exceptions** caught by routers and converted to HTTP errors

## Development Workflows

```sh
# Start PostgreSQL
docker-compose up -d

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
uv run poe test        # Run tests with pytest (80% coverage required)
uv run poe check-fast  # Checks without tests

# Generate new migration
uv run alembic revision --autogenerate -m "description"
```

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
2. Define domain exceptions in a dedicated exceptions module

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
- 80% coverage minimum (branch coverage enabled)
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
- OpenAI-compatible message format (role/content/tool_calls/tool_call_id)
- Cursor-based pagination on all list endpoints
- 404 (not 403) for cross-tenant resource access attempts

## Project Structure

```
Mini-Agent-Platform/
├── agent_platform/
│   ├── api/
│   │   ├── routers/           # FastAPI route handlers
│   │   ├── server.py          # App factory, middleware
│   │   └── static/            # Swagger/ReDoc assets
│   ├── auth/
│   │   └── api_key.py         # API key → tenant_id auth
│   ├── data_models/
│   │   ├── base.py            # SharedBaseModel (camelCase)
│   │   └── pagination.py      # Cursor-based pagination
│   ├── db/
│   │   ├── base.py            # SQLAlchemy Base
│   │   ├── models/            # ORM models
│   │   └── session.py         # Async session factory
│   ├── repositories/          # Data access layer
│   ├── services/              # Business logic
│   ├── exceptions/            # Domain exceptions
│   ├── settings.py            # Pydantic BaseSettings
│   └── containers.py          # DI container (logging)
├── alembic/                   # Database migrations
├── tests/                     # Mirrors source structure
├── docker-compose.yml         # PostgreSQL
├── Dockerfile                 # Multi-stage build
└── pyproject.toml             # Dependencies & tooling
```

## Environment Variables

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_platform
API_KEYS={"sk-tenant1-secret": "tenant_1", "sk-tenant2-secret": "tenant_2"}
APP_NAME=agent-platform
DEBUG=false
LOG_LEVEL=INFO
```
