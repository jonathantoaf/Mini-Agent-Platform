![CI](https://github.com/jonathantoaf/Mini-Agent-Platform/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

# Mini Agent Platform

A multi-tenant backend API for managing AI agents with configurable tools. Agents run through a deterministic LLM pipeline with multi-step tool calling, prompt injection guardrails, and execution history tracking.

The system enforces tenant isolation at two independent layers (application filtering + PostgreSQL RLS), runs agents through a multi-step tool-calling loop with a deterministic mock LLM for fully reproducible execution, and maintains 100% test coverage with dedicated RLS integration tests.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Agent Execution Pipeline](#agent-execution-pipeline)
- [Design Decisions](#design-decisions)
- [Security](#security)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Development Workflow](#development-workflow)
- [Testing Strategy](#testing-strategy)
- [CI/CD](#cicd)
- [Tech Stack](#tech-stack)

---

## Prerequisites

**With Docker** (quickest way to run everything):
- Docker & Docker Compose

**Without Docker** (local development):
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- PostgreSQL 16 (or use the Docker Compose postgres service)

---

## Quick Start

```bash
docker-compose up --build
```

That's it. PostgreSQL starts, migrations run, and the API is live at `http://localhost:5000`.

```bash
# Verify it's running
curl http://localhost:5000/health
# {"status":"OK"}

# Try an authenticated request
curl -H "X-API-Key: sk-tenant1-secret" http://localhost:5000/api/v1/tools
# {"items":[],"nextCursor":null,"hasMore":false}
```

For local development without Docker for the app:

```bash
docker-compose up -d postgres   # Just the database
uv sync                         # Install dependencies
cp .env.example .env            # Defaults work with docker-compose postgres
uv run alembic upgrade head     # Run migrations
uv run python main.py           # Start server on :5000
```

> Interactive API docs at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Architecture

Every request flows through authentication, then a strict layered architecture where no layer skips levels:

```mermaid
flowchart LR
    Client --> Auth --> Router --> Service --> Repository --> PostgreSQL
```

| Layer | What it does | Where |
|-------|-------------|-------|
| **Router** | HTTP handling, request validation, response serialization. No business logic here. | `api/routers/` |
| **Service** | Business logic, orchestration, domain exceptions. Completely transport-agnostic. | `services/` |
| **Repository** | SQLAlchemy queries, cursor pagination. Every query filters by `tenant_id`. | `repositories/` |
| **DB Model** | Schema definition, relationships, constraints. | `db/models/` |

**Dependency injection** uses a hybrid approach: a `dependency-injector` Container manages singletons (DB engine, guardrail, LLM adapter, tool executor) while FastAPI's `Depends()` handles per-request components (session, repositories, services). I went with this split because some things should live for the app's lifetime, but database sessions and anything touching tenant context need to be scoped per request for isolation. The `get_session()` dependency sets the RLS tenant context before yielding, so every query in that request is automatically scoped.

<details open>
<summary><strong>Project structure</strong></summary>

```
agent_platform/
├── api/
│   ├── routers/              # HTTP endpoints (agents, tools, run, executions, health)
│   ├── dependencies.py       # DI factories: session with RLS context, service constructors
│   └── server.py             # App factory, middleware, exception handlers
├── auth/
│   └── api_key.py            # X-API-Key -> tenant_id resolution (cached at startup)
├── data_models/
│   ├── base.py               # SharedBaseModel (auto snake_case -> camelCase)
│   ├── agent.py              # Agent Create/Update/Response schemas
│   ├── tool.py               # Tool Create/Update/Response schemas
│   ├── run.py                # RunRequest/Response, ChatMessage, ToolCallRecord
│   ├── execution.py          # ExecutionResponse schema
│   └── pagination.py         # Cursor encode/decode + PaginatedResponse[T]
├── db/
│   ├── models/               # SQLAlchemy ORM (Agent, Tool, Execution, agent_tools)
│   ├── base.py               # Declarative base
│   └── session.py            # Async session factory with lifecycle management
├── repositories/             # Data access layer (cursor pagination, tenant filtering)
├── services/
│   ├── run/                  # Agent execution pipeline
│   │   ├── guardrail.py      # Prompt injection detection (11 regex patterns)
│   │   ├── prompt_builder.py # Structured prompt construction (system + tools + user)
│   │   ├── mock_llm.py       # Deterministic LLM adapter (OpenAI-compatible interface)
│   │   ├── mock_tool_executor.py  # Mock tool execution
│   │   └── run_service.py    # Agentic loop orchestrator
│   ├── agent_service.py      # Agent CRUD + tool assignment
│   ├── tool_service.py       # Tool CRUD
│   └── execution_service.py  # Execution history retrieval
├── exceptions/               # Domain exception hierarchy (not HTTP exceptions)
├── containers.py             # DI container (singletons + resource lifecycle)
├── settings.py               # Pydantic BaseSettings (env + .env)
└── logging_context.py        # contextvars for request_id + tenant_id propagation
```
</details>

---

## Agent Execution Pipeline

### Pipeline Components

| Component | What it does | Design rationale |
|-----------|-------------|--------------------------|
| **PromptInjectionGuardrail** | Screens user input against 11 compiled regex patterns | Deterministic, local, no external calls. A production system would add an LLM-based classifier on top |
| **PromptBuilder** | Builds structured prompts: system instructions, tool descriptions, user input | Clear separation between prompt sections matters for LLM reliability |
| **MockLlmAdapter** | Returns deterministic responses via keyword matching | Implements `complete(messages, tools)`: the same interface a real LLM adapter would use. Follows OpenAI's tool-calling structure, so swapping to a real provider changes nothing in the pipeline |
| **MockToolExecutor** | Returns mock results for tool calls | Same idea: `execute(name, args)` is ready for real integrations |
| **RunService** | Orchestrates the loop with configurable max iterations (default: 10) | Coordinates everything, enforces the loop safeguard, stores execution history |

### How the Mock LLM Works

The `MockLlmAdapter` splits tool names on `-` and `_` to extract keywords, then checks if any keyword appears in the user's task. If a matching tool hasn't been called yet, it requests that tool. Once all matches are exhausted, it produces a final response.

| Tool Name | Keywords | Task | Match? |
|-----------|----------|------|--------|
| `web-search` | `web`, `search` | "**Search** for the latest trends" | Yes: "search" appears in task |
| `data-analyzer` | `data`, `analyzer` | "Search for the latest trends" | No match |
| `code_review` | `code`, `review` | "**Review** my pull request" | Yes: "review" appears in task |

This gives fully reproducible multi-turn conversations with zero external API calls: every test, CI run, and demo produces identical results. And because the `complete()` interface mirrors the OpenAI chat completions contract, replacing the mock with a real LLM adapter is a drop-in change.

---

## Design Decisions

### 1. Two-Layer Tenant Isolation (Application + PostgreSQL RLS)

Application-level filtering alone means a single missed `WHERE` clause leaks data across tenants. I added PostgreSQL Row-Level Security on top: every table has an RLS policy that checks `tenant_id` against a session-level variable set per request. If the app layer has a bug, the database still blocks cross-tenant access. The trade-off is needing two database roles (`postgres` for migrations, `app_user` for runtime) since superusers bypass RLS, but that's the only correct way to do it.

### 2. Cursor-Based Pagination Over Offset

Offset pagination (`LIMIT/OFFSET`) breaks under concurrent writes: rows get skipped or duplicated as new records shift the offset window. I went with cursor-based (keyset) pagination using a `(created_at, id)` composite key. Cursors are Base64-encoded JSON, opaque to clients. You lose "jump to page N," but in practice most API consumers page forward sequentially, and stability matters more than random access.

### 3. OpenAI-Compatible Tool-Calling Structure in Mocks

Rather than inventing a custom message format, all data models (`ChatMessage`, `ToolCallData`, `FunctionCall`, `ToolDefinition`) follow OpenAI's chat completions shape. The mock LLM's `complete(messages, tools)` mirrors the real API contract, so swapping to a real provider is a drop-in change.

### 4. Domain Exceptions, Not HTTP Exceptions in Services

FastAPI makes it tempting to raise `HTTPException` directly from services. I didn't: services raise domain exceptions like `AgentNotFoundError` and `PromptInjectionError`, and routers catch those to map to HTTP status codes. The service layer is completely transport-agnostic. You could wire it to a gRPC interface, a CLI, or a background worker without touching any business logic.

### 5. Database Constraint Uniqueness, Not Check-Then-Act

Checking "does this name exist?" before inserting creates a TOCTOU race condition: two concurrent requests can both pass the check and both insert. Instead, I rely on PostgreSQL `UNIQUE` constraints and catch `IntegrityError` at the service layer, converting it to an `AlreadyExistsError`. The error message is slightly less specific, but correctness under concurrency is guaranteed without any locking.

### 6. 404 for Cross-Tenant Access, Never 403

Returning `403 Forbidden` when a tenant tries to access another tenant's resource confirms the resource exists: that's an information leak. I always return `404 Not Found`. From the caller's perspective, resources outside their tenant simply don't exist.

### 7. camelCase API Responses with snake_case Internals

Python convention is `snake_case`, but frontend and mobile consumers expect `camelCase` in JSON. `SharedBaseModel` uses `pyhumps` as a Pydantic alias generator to handle the translation automatically.

### 8. Structured Logging with Request Correlation

In a multi-tenant system, "an error occurred" is useless without context. Every log line carries a `request_id` (8-char hex) and `tenant_id` via Python `contextvars`, which propagate automatically through async call chains. No explicit parameter threading needed.

### 9. Two Database Roles (Superuser for DDL, App User for Runtime)

PostgreSQL superusers bypass RLS entirely. If the app connects as `postgres`, the RLS policies do nothing. Migrations run as `postgres` (needs DDL privileges), but the app connects as `app_user` (non-superuser) so RLS is actually enforced at runtime. It means managing two connection strings (`DATABASE_URL` vs `DATABASE_MIGRATION_URL`), but there's no other way to make RLS real.

### 10. Hybrid DI: Container Singletons + FastAPI Per-Request

Some things (DB engine, guardrail, LLM adapter) should be created once and shared. Others (database sessions, repositories) must be scoped per-request for transaction isolation. I use `dependency-injector`'s `DeclarativeContainer` for the singletons and FastAPI's `Depends()` for per-request components. The `get_session()` dependency sets the RLS tenant context before yielding. This avoids the "service locator" anti-pattern while keeping startup costs low and request isolation clean.

---

## Security

### Multi-Tenant Isolation

Tenant isolation works at two independent layers: if one fails, the other still blocks cross-tenant access.

```
+-----------------------------------------------------+
|  Layer 1: Application                               |
|  Every repository query includes WHERE tenant_id=?  |
|  TenantId extracted from API key per request        |
+-----------------------------------------------------+
|  Layer 2: PostgreSQL RLS                            |
|  SET LOCAL app.current_tenant_id = ? per session    |
|  RLS policy: tenant_id = current_setting(...)       |
|  Applied to: agents, tools, executions              |
|  agent_tools: protected by FK to RLS parents        |
+-----------------------------------------------------+
```

### Prompt Injection Guardrails

The guardrail screens user input against 11 compiled regex patterns before it reaches the LLM:

- Ignore/disregard/forget previous instructions
- "You are now" / "Pretend to be" role hijacking
- `system:` prefix injection
- Override/reveal instructions/rules
- XML tag injection (`<system>`)

This is a first-line heuristic defense: deterministic, local, zero-latency. A real production system would layer an LLM-based classifier on top for better coverage.

### Authentication

API keys map to tenant IDs via a JSON config loaded once at startup. Every request needs an `X-API-Key` header. Missing or invalid keys get `401 Unauthorized`.

| API Key | Tenant ID |
|---------|-----------|
| `sk-tenant1-secret` | `tenant_1` |
| `sk-tenant2-secret` | `tenant_2` |

---

## API Reference

15 endpoints under `/api/v1/`. All list endpoints support cursor-based pagination. The fastest way to see everything in action:

```bash
bash scripts/demo.sh
```

This runs 34 use cases end-to-end (CRUD, agent execution, pagination, prompt injection, cross-tenant isolation, auth errors), prints every request/response, and cleans up after itself.

### Endpoints

| Method | Path | Description | Success | Errors |
|--------|------|-------------|---------|--------|
| `GET` | `/` | Service info (name, version) | 200 | - |
| `GET` | `/health` | Health check | 200 | - |
| `POST` | `/api/v1/tools` | Create tool | 201 | 401, 409 |
| `GET` | `/api/v1/tools` | List tools (paginated, filter by `agentName`) | 200 | 401, 400 |
| `GET` | `/api/v1/tools/{id}` | Get tool | 200 | 401, 404 |
| `PATCH` | `/api/v1/tools/{id}` | Update tool | 200 | 401, 404, 409 |
| `DELETE` | `/api/v1/tools/{id}` | Delete tool | 204 | 401, 404 |
| `POST` | `/api/v1/agents` | Create agent (with tool assignments) | 201 | 401, 404, 409 |
| `GET` | `/api/v1/agents` | List agents (paginated, filter by `toolName`) | 200 | 401, 400 |
| `GET` | `/api/v1/agents/{id}` | Get agent | 200 | 401, 404 |
| `PATCH` | `/api/v1/agents/{id}` | Update agent | 200 | 401, 404, 409 |
| `DELETE` | `/api/v1/agents/{id}` | Delete agent | 204 | 401, 404 |
| `POST` | `/api/v1/agents/{id}/run` | Run agent through LLM pipeline | 200 | 401, 400, 404 |
| `GET` | `/api/v1/agents/{id}/executions` | List execution history (paginated) | 200 | 401, 400, 404 |
| `GET` | `/api/v1/executions/{id}` | Get execution details | 200 | 401, 404 |

<details open>
<summary><strong>End-to-end walkthrough (curl examples)</strong></summary>

**Step 1: Create a tool**

```bash
curl -s -X POST http://localhost:5000/api/v1/tools \
  -H "X-API-Key: sk-tenant1-secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "web-search", "description": "Search the web for information"}' | jq
```

```json
{
  "id": "a1b2c3d4-...",
  "name": "web-search",
  "description": "Search the web for information",
  "createdAt": "2026-03-27T10:00:00Z",
  "updatedAt": "2026-03-27T10:00:00Z"
}
```

**Step 2: Create an agent with that tool**

```bash
curl -s -X POST http://localhost:5000/api/v1/agents \
  -H "X-API-Key: sk-tenant1-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Assistant",
    "role": "research analyst",
    "description": "Analyzes topics by searching the web and summarizing findings",
    "toolIds": ["<tool-id-from-step-1>"]
  }' | jq
```

```json
{
  "id": "e5f6g7h8-...",
  "name": "Research Assistant",
  "role": "research analyst",
  "description": "Analyzes topics by searching the web and summarizing findings",
  "tools": [
    {
      "id": "a1b2c3d4-...",
      "name": "web-search",
      "description": "Search the web for information"
    }
  ],
  "createdAt": "2026-03-27T10:00:01Z",
  "updatedAt": "2026-03-27T10:00:01Z"
}
```

**Step 3: Run the agent**

```bash
curl -s -X POST http://localhost:5000/api/v1/agents/<agent-id>/run \
  -H "X-API-Key: sk-tenant1-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Search for the latest trends in AI agents",
    "model": "gpt-4o"
  }' | jq
```

```json
{
  "executionId": "x9y0z1a2-...",
  "agentId": "e5f6g7h8-...",
  "task": "Search for the latest trends in AI agents",
  "model": "gpt-4o",
  "finalResponse": "Based on the tool results:\n- Mock result for web-search with arguments: {\"input\": \"Search for the latest trends in AI agents\"}\nTask completed successfully.",
  "toolCalls": [
    {
      "toolCallId": "call_abc123def456",
      "toolName": "web-search",
      "arguments": "{\"input\": \"Search for the latest trends in AI agents\"}",
      "result": "Mock result for web-search with arguments: {\"input\": \"Search for the latest trends in AI agents\"}"
    }
  ],
  "messages": ["...full conversation history..."],
  "createdAt": "2026-03-27T10:00:02Z"
}
```

**Step 4: View execution history**

```bash
curl -s http://localhost:5000/api/v1/agents/<agent-id>/executions \
  -H "X-API-Key: sk-tenant1-secret" | jq
```

```json
{
  "items": [
    {
      "executionId": "x9y0z1a2-...",
      "agentId": "e5f6g7h8-...",
      "task": "Search for the latest trends in AI agents",
      "model": "gpt-4o",
      "finalResponse": "Based on the tool results:\n- Mock result for web-search...\nTask completed successfully.",
      "toolCalls": [
        {
          "toolCallId": "call_abc123def456",
          "toolName": "web-search",
          "arguments": "{\"input\": \"Search for the latest trends in AI agents\"}",
          "result": "Mock result for web-search with arguments: ..."
        }
      ],
      "messages": ["...full conversation history..."],
      "createdAt": "2026-03-27T10:00:02Z"
    }
  ],
  "nextCursor": null,
  "hasMore": false
}
```

**Step 5: Get execution details**

```bash
curl -s http://localhost:5000/api/v1/executions/<execution-id> \
  -H "X-API-Key: sk-tenant1-secret" | jq
```

</details>

---

## Deployment

### Docker Compose

`docker-compose.yml` runs two services:

- **postgres**: PostgreSQL 16 Alpine with health checks (`pg_isready`) and a persistent volume
- **app**: Multi-stage Dockerfile, waits for Postgres health, runs `alembic upgrade head && python main.py`

Two database roles, deliberately:
- `postgres` (superuser): runs migrations, creates `app_user` role and RLS policies
- `app_user` (non-superuser): runtime connections where RLS is actually enforced

### Multi-Stage Dockerfile

```
+-- Build Stage ------------------------------------------+
|  python:3.12-slim-bookworm                              |
|  Install uv -> copy lockfile -> uv sync --frozen        |
|  --no-dev --no-install-project                          |
|  Result: .venv with production deps only                |
+-- Production Stage -------------------------------------+
|  python:3.12-slim-bookworm (clean)                      |
|  Copy .venv + source from build stage                   |
|  Build args: COMMIT_ID, BUILD_DATE (traceability)       |
|  CMD: python main.py                                    |
+---------------------------------------------------------+
```

The frozen lockfile (`uv sync --frozen`) means builds are reproducible. No dev dependencies end up in the production image.

---

## Development Workflow

### Commands

All tooling runs through `uv` and `poethepoet`:

| Command | What it does |
|---------|-------------|
| `uv run poe format` | Format code with Ruff (line-length: 100) |
| `uv run poe lint` | Lint with auto-fix (20+ rule categories) |
| `uv run poe typecheck` | Static type checking with ty |
| `uv run poe test` | Run tests with 100% coverage enforcement + branch coverage |
| `uv run poe check` | **All of the above, in sequence.** This is what CI runs. |
| `uv run poe check-fast` | Everything except tests: sub-second feedback loop |

My inner loop: edit code, run `check-fast` (takes seconds), then `test` when I'm confident, then commit.

### Migrations

```bash
uv run alembic revision --autogenerate -m "add new_table"   # Generate from model changes
uv run alembic upgrade head                                  # Apply pending migrations
uv run alembic downgrade -1                                  # Rollback last migration
```

New DB models must be imported in `db/models/__init__.py` for Alembic's autogenerate to pick them up.

### Package Management

Dependencies managed with `uv`, locked in `uv.lock`. The `--frozen` flag in CI and Docker builds prevents lockfile drift.

---

## Testing Strategy

### Philosophy

All application tests are unit tests with mocked dependencies. Services and routers are tested in isolation using `AsyncMock` and FastAPI's `dependency_overrides`. The one exception is `test_rls.py`, which hits a real PostgreSQL instance to verify Row-Level Security actually works at the database level.

### Test Pyramid

| Level | What | How | Where |
|-------|------|-----|-------|
| **Unit** (Router) | HTTP handling, error mapping, response shapes | Mocked services via `dependency_overrides` | `tests/routers/` |
| **Unit** (Service) | Business logic, edge cases, exception paths | `AsyncMock` repositories | `tests/services/` |
| **Unit** (Pipeline) | Guardrail patterns, mock LLM behavior, prompt construction | Direct class testing | `tests/services/run/` |
| **Integration** (RLS) | Database-level tenant isolation | Real PostgreSQL + raw SQL | `tests/routers/test_rls.py` |

### 100% Coverage with Strategic Exclusions

Coverage is enforced at 100% with branch coverage. These are excluded because they're declarative with no logic to test:

| Excluded | Why |
|----------|-----|
| `data_models/` | Pydantic schemas: testing them means testing Pydantic itself |
| `db/models/` | ORM models, purely declarative |
| `repositories/` | Data access with no business logic |
| `exceptions/` | Simple exception classes |

### RLS Tests

`test_rls.py` is the only test hitting a real database. It confirms:

- Tenant 1 can't read Tenant 2's resources through the API
- RLS policies block cross-tenant queries even with direct SQL
- The `WITH CHECK` clause rejects mismatched `tenant_id` inserts

```bash
uv run poe test     # Run with 100% coverage enforcement
uv run poe check    # Full suite: format + lint + typecheck + test
```

---

## CI/CD

GitHub Actions runs on every push to `main`, all PRs, and manual dispatch.

**`check`**: Spins up PostgreSQL 16, installs dependencies (frozen lockfile), runs migrations as `postgres` superuser (creates `app_user` role + RLS policies), then runs `uv run poe check` (format + lint + typecheck + test with 100% coverage).

**`build`**: Verifies the multi-stage Docker image builds. Uses GHA cache for layer caching. No push: this validates the Dockerfile, not the deployment.

---

<details open>
<summary><strong>Configuration reference</strong></summary>

All settings loaded from environment variables (or `.env`) via Pydantic BaseSettings.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Runtime connection string (non-superuser) | `postgresql+asyncpg://app_user:app_user@localhost:5432/agent_platform` |
| `DATABASE_MIGRATION_URL` | Migration connection string (superuser) | `postgresql+asyncpg://postgres:postgres@localhost:5432/agent_platform` |
| `API_KEYS` | JSON mapping of API keys to tenant IDs | `{}` |
| `APP_NAME` | Application name | `agent-platform` |
| `APP_VERSION` | Application version | `1.0.0` |
| `DEBUG` | Debug mode (SQL echo, verbose logging) | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SERVER_HOST` | Bind address | `0.0.0.0` |
| `SERVER_PORT` | Server port | `5000` |
| `DATABASE_POOL_SIZE` | Connection pool size | `5` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `10` |
| `PAGINATION_DEFAULT_LIMIT` | Default page size | `20` |
| `PAGINATION_MAX_LIMIT` | Max page size | `100` |
| `RUN_MAX_ITERATIONS` | Max loop iterations (prevents runaway execution) | `10` |
| `ALLOWED_MODELS` | JSON array of allowed model names | `["gpt-4o", "gpt-4o-mini", ...]` |

</details>

---

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| Python 3.12+ | Async runtime with modern type hints |
| FastAPI | Async web framework with auto OpenAPI docs |
| SQLAlchemy 2.0 (async) | ORM with full async support via asyncpg |
| PostgreSQL 16 | RLS support, battle-tested for multi-tenant |
| Alembic | SQLAlchemy-native migrations with autogenerate |
| Pydantic v2 | Validation with auto camelCase serialization |
| dependency-injector | Declarative DI container with lifecycle management |
| uv | Fast, lockfile-based package management |
| Ruff | Linter + formatter (replaces flake8 + black + isort) |
| ty | Lightweight Python type checker |
| pytest | Testing with fixtures, async support, coverage |
| Docker | Multi-stage builds, minimal production images |
| GitHub Actions | CI with native PostgreSQL service containers |

---

## License

MIT
