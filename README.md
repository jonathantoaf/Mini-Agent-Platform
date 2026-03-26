# Mini Agent Platform

A multi-tenant backend API for managing AI agents with configurable tools. Agents can be run through a mock LLM pipeline that supports multi-step tool calling, prompt injection guardrails, and execution history tracking.

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with async support
- **Database**: PostgreSQL 16 with [SQLAlchemy 2.0](https://www.sqlalchemy.org/) async (asyncpg)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Package Manager**: [uv](https://docs.astral.sh/uv/)
- **Code Quality**: [Ruff](https://docs.astral.sh/ruff/) (format/lint), [ty](https://github.com/astral-sh/ty) (typecheck)
- **Testing**: [pytest](https://docs.pytest.org/) with 80% coverage requirement
- **Task Runner**: [poethepoet](https://poethepoet.natn.io/)

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose (for PostgreSQL)

## Getting Started

### 1. Start PostgreSQL

```sh
docker-compose up -d
```

### 2. Install Dependencies

```sh
uv sync
```

### 3. Configure Environment

```sh
cp .env.example .env
# Edit .env if needed (defaults work with docker-compose)
```

### 4. Run Migrations

```sh
uv run alembic upgrade head
```

### 5. Start the Server

```sh
uv run python main.py
```

The server will be available at http://localhost:5000

- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc

## API Authentication

All API endpoints require an `X-API-Key` header. API keys map to tenant IDs, ensuring complete data isolation between tenants.

Default keys (from `.env.example`):

| API Key | Tenant ID |
|---------|-----------|
| `sk-tenant1-secret` | `tenant_1` |
| `sk-tenant2-secret` | `tenant_2` |

Example:
```sh
curl -H "X-API-Key: sk-tenant1-secret" http://localhost:5000/api/v1/agents
```

## Development

### Available Commands

```sh
uv run poe check       # Run all checks (format, lint, typecheck, test)
uv run poe check-fast  # Checks without tests
uv run poe format      # Format code with ruff
uv run poe lint        # Lint code with auto-fix
uv run poe typecheck   # Type check with ty
uv run poe test        # Run tests with coverage

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

### Project Structure

```
Mini-Agent-Platform/
├── agent_platform/
│   ├── api/routers/           # FastAPI route handlers
│   ├── auth/                  # API key authentication
│   ├── data_models/           # Pydantic schemas (camelCase serialization)
│   ├── db/models/             # SQLAlchemy ORM models
│   ├── repositories/          # Data access layer
│   ├── services/              # Business logic
│   └── settings.py            # Environment configuration
├── alembic/                   # Database migrations
├── tests/                     # Test suite
├── docker-compose.yml         # PostgreSQL setup
└── pyproject.toml             # Dependencies & tooling
```

## Docker

```sh
# Build the app image
docker build -t agent-platform .

# Run with env file
docker run -p 5000:5000 --env-file .env agent-platform
```

## License

MIT
