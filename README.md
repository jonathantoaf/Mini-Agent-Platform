![CI](https://github.com/jonathantoaf/Mini-Agent-Platform/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

# Mini Agent Platform

A production-grade, multi-tenant backend API for managing AI agents with configurable tools. Agents run through a deterministic LLM pipeline that supports multi-step tool calling, prompt injection guardrails, and full execution history tracking.

Every layer -- from database-enforced tenant isolation (PostgreSQL RLS) to cursor-based pagination and 100% test coverage -- reflects patterns you'd find in a production microservice.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Agent Execution Pipeline](#agent-execution-pipeline)
- [Design Decisions](#design-decisions)
- [Security](#security)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Development Workflow](#development-workflow)
- [Testing Strategy](#testing-strategy)
- [CI/CD Pipeline](#cicd-pipeline)
- [Configuration Reference](#configuration-reference)
- [Future Improvements](#future-improvements)
- [Tech Stack](#tech-stack)

---

## Architecture Overview

### Request Flow

Every request passes through authentication, middleware, and a strict layered architecture before reaching the database -- where Row-Level Security provides a final enforcement barrier.

```mermaid
flowchart LR
    Client -->|X-API-Key| Auth[Auth Middleware]
    Auth -->|tenant_id| MW[Request Middleware<br/>request_id + logging]
    MW --> Router
    Router --> Service
    Service --> Repository
    Repository -->|SET app.current_tenant_id| DB[(PostgreSQL 16<br/>+ RLS Policies)]

    style DB fill:#336791,color:#fff
    style Auth fill:#e74c3c,color:#fff
```

### Layered Architecture

Each layer has a single responsibility and a strict dependency direction. No layer skips levels.

| Layer | Responsibility | Key Principle | Location |
|-------|---------------|---------------|----------|
| **Router** | HTTP handling, request validation, response serialization | Never contains business logic or database queries | `api/routers/` |
| **Service** | Business logic, orchestration, domain exception raising | Transport-agnostic -- could serve gRPC or CLI tomorrow | `services/` |
| **Repository** | Data access, query construction, pagination | All queries filter by `tenant_id` -- no exceptions | `repositories/` |
| **DB Model** | Schema definition, relationships, constraints | Source of truth for database structure | `db/models/` |

### Dependency Injection

The system uses a hybrid DI approach: a `dependency-injector` **Container** manages singleton lifecycles (DB engine, guardrail, LLM adapter, tool executor), while FastAPI's `Depends()` provides per-request components (session, repositories, services). This gives us efficient resource sharing without coupling services to a specific transport layer.

### Project Structure

```
agent_platform/
├── api/
│   ├── routers/              # HTTP endpoints (agents, tools, run, executions, health)
│   ├── dependencies.py       # DI factories -- session with RLS context, service constructors
│   └── server.py             # App factory, middleware, exception handlers
├── auth/
│   └── api_key.py            # X-API-Key → tenant_id resolution (cached at startup)
├── data_models/
│   ├── base.py               # SharedBaseModel (auto snake_case → camelCase)
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

---

## Agent Execution Pipeline

The run pipeline is the heart of the system. It orchestrates prompt construction, LLM interaction, tool execution, and history storage in a controlled loop with safety guardrails.

```mermaid
sequenceDiagram
    participant C as Client
    participant R as RunRouter
    participant S as RunService
    participant G as Guardrail
    participant PB as PromptBuilder
    participant LLM as MockLlmAdapter
    participant TE as ToolExecutor
    participant DB as Database

    C->>R: POST /agents/{id}/run
    R->>S: run_agent(tenant_id, agent_id, request)
    S->>S: Validate model against allowed list
    S->>DB: Load agent + assigned tools
    S->>G: check(task) — reject injection attempts
    S->>PB: build_messages(agent, task)
    PB-->>S: [system_prompt, user_message]
    S->>PB: build_tools(agent)
    PB-->>S: [tool_definitions]

    loop Until final response or max iterations
        S->>LLM: complete(messages, tools)
        alt Tool call requested
            LLM-->>S: assistant_msg with tool_calls
            S->>S: Validate tool is assigned to agent
            S->>TE: execute(tool_name, arguments)
            TE-->>S: tool result
            S->>S: Append tool result to messages
        else Final response
            LLM-->>S: assistant_msg with content
        end
    end

    S->>DB: Store execution record
    S-->>R: RunResponse
    R-->>C: 200 OK + execution details
```

### Pipeline Components

| Component | Responsibility | Design Rationale |
|-----------|---------------|-----------------|
| **PromptInjectionGuardrail** | Screens user input against 11 regex patterns for common injection attempts | Deterministic, local, no external calls. Demonstrates security awareness -- a production system would layer this with an LLM-based classifier |
| **PromptBuilder** | Constructs structured prompts with clear separation: system instructions, tool descriptions, user input | Clean prompt structure is critical for LLM reliability. The builder formats agent metadata and tools into the system prompt |
| **MockLlmAdapter** | Returns deterministic responses using keyword matching between tool names and user task | Implements the same `complete(messages, tools)` interface a real LLM adapter would. Uses OpenAI's tool-calling structure so swapping to a real provider requires zero changes to the pipeline |
| **MockToolExecutor** | Returns deterministic mock results for tool calls | Same pattern -- the `execute(name, args)` interface is ready for real tool integrations |
| **RunService** | Orchestrates the full loop with configurable max iterations (default: 10) | Coordinates all components, enforces the loop safeguard, and stores execution history |

### How the Mock LLM Works

The `MockLlmAdapter` splits tool names on `-` and `_` to extract keywords, then checks if any keyword appears in the user's task. If a matching tool hasn't been called yet, it requests that tool. Once all matching tools have been called (or none match), it produces a final response summarizing the results.

This design enables **fully deterministic, reproducible multi-turn conversations** without any external API calls -- ideal for testing, CI, and demos. The `complete()` interface follows the OpenAI chat completions contract, so replacing the mock with a real LLM adapter is a drop-in change.

---

## Design Decisions

Each decision below follows a lightweight Architecture Decision Record format: what was decided, why, and what trade-off was accepted.

### 1. Two-Layer Tenant Isolation (Application + PostgreSQL RLS)

**Context**: The assignment requires tenant isolation via a `tenant_id` column. Application-level filtering works, but a single missed `WHERE` clause leaks data across tenants.

**Decision**: Implement tenant isolation at **both** the application layer (repository queries filter by `tenant_id`) **and** the database layer (PostgreSQL Row-Level Security policies on all tables).

**Trade-off**: Requires two database roles -- `postgres` (superuser) for DDL migrations and `app_user` (non-superuser) for runtime, since superusers bypass RLS. Worth it for defense-in-depth.

### 2. Cursor-Based Pagination Over Offset

**Context**: Offset pagination (`LIMIT/OFFSET`) breaks under concurrent writes -- rows get skipped or duplicated as new records shift the offset window.

**Decision**: Use cursor-based (keyset) pagination with a `(created_at, id)` composite key. Cursors are Base64-encoded JSON, opaque to clients.

**Trade-off**: No "jump to page N" capability. In practice, most API consumers page forward sequentially -- and stability matters more than random access.

### 3. OpenAI-Compatible Tool-Calling Structure in Mocks

**Context**: The mock LLM needs a message and tool-calling format. Rather than inventing a custom schema, the system adopts OpenAI's chat completions structure -- `ChatMessage` with `role`, `content`, `tool_calls`, and `tool_call_id`.

**Decision**: All data models (`ChatMessage`, `ToolCallData`, `FunctionCall`, `ToolDefinition`) follow OpenAI's API shape. The mock LLM's `complete(messages, tools)` method mirrors the real API contract.

**Rationale**: When the time comes to integrate a real LLM provider (OpenAI, Anthropic, etc.), the entire pipeline -- prompt builder, execution loop, execution storage -- requires zero structural changes. Only the adapter implementation changes. This is the [Adapter Pattern](https://refactoring.guru/design-patterns/adapter) applied to LLM integration.

### 4. Domain Exceptions, Not HTTP Exceptions in Services

**Context**: FastAPI makes it easy to raise `HTTPException` directly from services. But this couples business logic to HTTP transport.

**Decision**: Services raise domain exceptions (`AgentNotFoundError`, `ToolAlreadyExistsError`, `PromptInjectionError`). Routers catch these and map them to HTTP status codes.

**Rationale**: The same service layer could serve a gRPC interface, a CLI, or a background worker without changing a single line. The exception hierarchy also provides a clear, typed contract for error handling.

### 5. Database Constraint Uniqueness, Not Check-Then-Act

**Context**: Checking "does this name exist?" before inserting creates a TOCTOU (time-of-check-to-time-of-use) race condition under concurrent requests.

**Decision**: Rely on PostgreSQL `UNIQUE` constraints and catch `IntegrityError` at the service layer, converting it to an `AlreadyExistsError`.

**Trade-off**: The error message is less specific (we catch a generic `IntegrityError`), but correctness under concurrency is guaranteed.

### 6. 404 for Cross-Tenant Access, Never 403

**Context**: Returning `403 Forbidden` when a tenant tries to access another tenant's resource confirms the resource exists -- an information leak.

**Decision**: Always return `404 Not Found` for "not found or not yours." From the caller's perspective, resources outside their tenant simply don't exist.

### 7. camelCase API Responses with snake_case Internals

**Context**: Python convention is `snake_case`. Frontend and mobile teams expect `camelCase` in JSON APIs.

**Decision**: `SharedBaseModel` uses `pyhumps` as a Pydantic alias generator. All API responses are automatically serialized to `camelCase`. Internal code stays `snake_case`.

**Rationale**: A small detail, but it signals awareness of API consumers and reduces friction for frontend integration.

### 8. Structured Logging with Request Correlation

**Context**: In a multi-tenant system, debugging without request context is impossible at scale. "An error occurred" means nothing without knowing which tenant, which request.

**Decision**: Every log line carries `request_id` (8-char hex) and `tenant_id` via Python `contextvars`. These propagate automatically through async call chains without explicit parameter threading.

**Rationale**: This is the pattern used at companies like Stripe and Datadog. It's the difference between "we had an error" and "tenant_2's request abc123ef failed at the guardrail check."

### 9. Two Database Roles (Superuser for DDL, App User for Runtime)

**Context**: PostgreSQL superusers bypass RLS entirely. If the application connects as `postgres`, RLS policies are decorative.

**Decision**: Migrations run as `postgres` (superuser) for DDL privileges. The application connects as `app_user` (non-superuser) so RLS policies are enforced at runtime.

**Trade-off**: Requires managing two connection strings (`DATABASE_URL` vs `DATABASE_MIGRATION_URL`), but this is the only correct way to use RLS.

### 10. Dependency Injection: Container Singletons + FastAPI Per-Request

**Context**: Some components (DB engine, guardrail, LLM adapter) should be created once and shared. Others (database session, repositories, services) must be scoped per-request for transaction isolation.

**Decision**: Use `dependency-injector`'s `DeclarativeContainer` for singletons and FastAPI's `Depends()` for per-request components. The `get_session()` dependency sets the RLS tenant context before yielding.

**Rationale**: This hybrid avoids the "service locator" anti-pattern while keeping startup costs low and request isolation clean.

---

## Security

### Multi-Tenant Isolation

The system enforces tenant isolation at two independent layers -- if one fails, the other still protects data.

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: Application                               │
│  Every repository query includes WHERE tenant_id=?  │
│  TenantId extracted from API key per request        │
├─────────────────────────────────────────────────────┤
│  Layer 2: PostgreSQL RLS                            │
│  SET LOCAL app.current_tenant_id = ? per session    │
│  RLS policy: tenant_id = current_setting(...)       │
│  Applied to: agents, tools, executions              │
│  agent_tools: protected by FK to RLS parents        │
└─────────────────────────────────────────────────────┘
```

### Prompt Injection Guardrails

The guardrail screens user input against 11 compiled regex patterns before it reaches the LLM:

- Ignore/disregard/forget previous instructions
- "You are now" / "Pretend to be" role hijacking
- `system:` prefix injection
- Override/reveal instructions/rules
- XML tag injection (`<system>`)

This is a **first-line heuristic defense** -- deterministic, local, and zero-latency. A production system would layer this with an LLM-based classifier for higher coverage.

### Authentication

API keys are mapped to tenant IDs via a JSON configuration loaded once at startup. Every request must include an `X-API-Key` header. Invalid or missing keys return `401 Unauthorized`.

| API Key | Tenant ID |
|---------|-----------|
| `sk-tenant1-secret` | `tenant_1` |
| `sk-tenant2-secret` | `tenant_2` |

---

## API Reference

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

### End-to-End Walkthrough

Here's a complete story: create a tool, create an agent with that tool, run the agent, and view the execution history.

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

The mock LLM is fully deterministic -- no randomness, no external calls. It splits each tool name on `-` and `_` to extract keywords, then checks if any keyword appears in the user's task:

| Tool Name | Extracted Keywords | Task | Match? |
|-----------|--------------------|------|--------|
| `web-search` | `web`, `search` | "**Search** for the latest trends" | Yes -- "search" found in task |
| `data-analyzer` | `data`, `analyzer` | "Search for the latest trends" | No -- neither keyword in task |
| `code_review` | `code`, `review` | "**Review** my pull request" | Yes -- "review" found in task |

In this example, the task contains "Search" which matches `web-search`, so the LLM requests a tool call. After the tool executes, the LLM is re-invoked -- since no more matching tools remain, it produces a final response summarizing the results. This makes every execution reproducible and safe for testing and CI.

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
      "finalResponse": "Based on the tool results:\n- Mock result for web-search with arguments: ...\nTask completed successfully.",
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

**Step 5: Get full execution details**

```bash
curl -s http://localhost:5000/api/v1/executions/<execution-id> \
  -H "X-API-Key: sk-tenant1-secret" | jq
```

> Interactive API docs are also available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose

### Option A: Docker Compose (Recommended)

One command starts PostgreSQL, runs migrations, and launches the server:

```bash
docker-compose up --build
```

The API is available at `http://localhost:5000`. Migrations run automatically on startup.

### Option B: Local Development

```bash
# 1. Start PostgreSQL
docker-compose up -d postgres

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env if needed (defaults work with docker-compose postgres)

# 4. Run database migrations
uv run alembic upgrade head

# 5. Start the server
uv run python main.py
```

### Verify

```bash
curl http://localhost:5000/health
# {"status":"OK"}

curl -H "X-API-Key: sk-tenant1-secret" http://localhost:5000/api/v1/tools
# {"items":[],"nextCursor":null,"hasMore":false}
```

---

## Deployment

### Docker Compose

The `docker-compose.yml` orchestrates two services:

- **postgres**: PostgreSQL 16 Alpine with health checks (`pg_isready`), persistent volume for data
- **app**: Builds from the multi-stage Dockerfile, waits for Postgres health, runs `alembic upgrade head && python main.py`

Two database roles are used deliberately:
- `postgres` (superuser) -- runs migrations, creates the `app_user` role and RLS policies
- `app_user` (non-superuser) -- runtime connections, RLS policies are enforced

### Multi-Stage Dockerfile

```
┌─ Build Stage ──────────────────────────────────────┐
│  python:3.12-slim-bookworm                         │
│  Install uv → copy lockfile → uv sync --frozen     │
│  --no-dev --no-install-project                     │
│  Result: .venv with production deps only           │
├─ Production Stage ─────────────────────────────────┤
│  python:3.12-slim-bookworm (clean)                 │
│  Copy .venv + source from build stage              │
│  Build args: COMMIT_ID, BUILD_DATE (traceability)  │
│  CMD: python main.py                               │
└────────────────────────────────────────────────────┘
```

The frozen lockfile (`uv sync --frozen`) ensures reproducible builds. No dev dependencies in the production image.

---

## Development Workflow

### Code Quality Toolchain

Every command runs through `uv` and `poethepoet`:

| Command | Tool | What it does |
|---------|------|-------------|
| `uv run poe format` | Ruff | Format code (line-length: 100) |
| `uv run poe lint` | Ruff | Lint with auto-fix (security, naming, complexity, imports -- 20+ rule categories) |
| `uv run poe typecheck` | ty | Static type checking on `agent_platform/` |
| `uv run poe test` | pytest | Run tests with 100% coverage enforcement + branch coverage |
| `uv run poe check` | All | **Runs all of the above in sequence.** This is what CI runs. |
| `uv run poe check-fast` | All except test | Quick feedback loop -- format, lint, typecheck without waiting for tests |
| `uv run poe clean` | - | Remove `__pycache__`, `.pytest_cache`, `.ruff_cache` |

### Developer Inner Loop

```
Edit code → uv run poe check-fast (seconds) → uv run poe test (with DB) → commit
```

`check-fast` gives sub-second feedback on formatting, lint, and types. Run the full `check` before pushing.

### Database Migrations

```bash
# Generate migration from model changes
uv run alembic revision --autogenerate -m "add new_table"

# Apply all pending migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1
```

New DB models must be imported in `db/models/__init__.py` for Alembic autogenerate to detect them.

### Package Management

Dependencies are managed with `uv` and locked in `uv.lock`. Install with `uv sync` (respects the lockfile for reproducibility). The `--frozen` flag in CI and Docker ensures no lockfile drift.

---

## Testing Strategy

### Philosophy

Tests run against a **real PostgreSQL instance** -- not SQLite, not mocks. Why?

- SQLite doesn't support RLS, JSON operators, or async drivers
- Mocked database tests that pass while the real migration fails is a known anti-pattern
- The cost of running PostgreSQL in CI (via service container) is negligible compared to the confidence it provides

### Test Pyramid

| Level | What | How | Location |
|-------|------|-----|----------|
| **Integration** (Router) | Full HTTP request/response cycle, tenant isolation, pagination | `TestClient` + real PostgreSQL | `tests/routers/` |
| **Unit** (Service) | Business logic, edge cases, exception paths | `AsyncMock` repositories | `tests/services/` |
| **Component** (Pipeline) | Guardrail patterns, mock LLM behavior, prompt construction | Direct class testing | `tests/services/run/` |
| **RLS** | Database-level tenant isolation independent of app code | Raw SQL assertions | `tests/routers/test_rls.py` |

### 100% Coverage with Strategic Exclusions

Coverage is enforced at 100% with branch coverage enabled. The following are excluded -- and here's why:

| Excluded | Reason |
|----------|--------|
| `data_models/` | Pydantic schemas are declarative. Testing them means testing Pydantic. |
| `db/models/` | ORM models are declarative. Tested implicitly through integration tests. |
| `repositories/` | Data access is tested through integration tests that hit real PostgreSQL. |
| `exceptions/` | Simple exception classes with no logic. |

### RLS Tests

Dedicated `test_rls.py` verifies tenant isolation at the **database level** -- not just the API level. These tests confirm that:

- Tenant 1 cannot read Tenant 2's resources via the API
- RLS policies block cross-tenant queries even with direct database access
- Mismatched `tenant_id` inserts are rejected by the `WITH CHECK` clause

### Running Tests

```bash
uv run poe test          # Run with 100% coverage enforcement
uv run poe check         # Full suite: format + lint + typecheck + test
```

---

## CI/CD Pipeline

GitHub Actions runs on every push to `main`, all pull requests, and manual dispatch.

### Jobs

**`check`** -- Spins up a PostgreSQL 16 service container, installs dependencies with frozen lockfile, runs migrations as `postgres` superuser (which creates the `app_user` role and RLS policies), then runs the full `uv run poe check` suite. The app connects as `app_user` so RLS is enforced during tests.

**`build`** -- Verifies the multi-stage Docker image builds successfully. Uses GitHub Actions cache for Docker layer caching. No push -- this job validates the Dockerfile, not the deployment.

The CI intentionally uses a **real PostgreSQL service container** rather than mocking the database. RLS policies, async drivers, and JSON operators all behave differently (or don't exist) in SQLite -- testing against the real thing is the only way to be sure.

---

## Configuration Reference

All settings are loaded from environment variables (or `.env` file) via Pydantic BaseSettings.

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async connection string for app runtime (non-superuser) | `postgresql+asyncpg://app_user:app_user@localhost:5432/agent_platform` |
| `DATABASE_MIGRATION_URL` | Async connection string for Alembic migrations (superuser) | `postgresql+asyncpg://postgres:postgres@localhost:5432/agent_platform` |
| `API_KEYS` | JSON mapping of API keys to tenant IDs | `{}` |
| `APP_NAME` | Application name (returned by `/` endpoint) | `agent-platform` |
| `APP_VERSION` | Application version | `1.0.0` |
| `DEBUG` | Enable debug mode (SQL echo, verbose logging) | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SERVER_HOST` | Server bind address | `0.0.0.0` |
| `SERVER_PORT` | Server port | `5000` |
| `DATABASE_POOL_SIZE` | Connection pool size | `5` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `10` |
| `PAGINATION_DEFAULT_LIMIT` | Default page size | `20` |
| `PAGINATION_MAX_LIMIT` | Maximum allowed page size | `100` |
| `RUN_MAX_ITERATIONS` | Max execution loop iterations (prevents infinite loops) | `10` |
| `ALLOWED_MODELS` | JSON array of allowed LLM model names | `["gpt-4o", "gpt-4o-mini", ...]` |

---

## Future Improvements

These are the natural next steps -- scoped out deliberately for this exercise, but designed into the architecture for easy addition.

### Production Readiness

- **Real LLM integration** -- The `MockLlmAdapter.complete()` interface is designed for drop-in replacement. Swap the mock with an OpenAI/Anthropic adapter without changing the pipeline.
- **JWT/OAuth2 authentication** with key rotation and token refresh
- **Rate limiting** per tenant (token bucket or sliding window)
- **OpenTelemetry tracing** for distributed observability across services
- **Async execution** with a background task queue (Celery/ARQ) and webhook callbacks for long-running agent tasks

### Scalability

- **Read replicas** for execution history queries (read-heavy workload)
- **Redis caching** for frequently accessed agents and tools
- **PgBouncer** connection pooling for high-concurrency scenarios
- **Horizontal scaling** with stateless app servers behind a load balancer

### Security

- **LLM-based prompt injection classifier** layered on top of the current regex approach for higher coverage
- **Audit logging** for all tenant data mutations (who changed what, when)
- **API key hashing** -- store hashed keys at rest, not plaintext
- **Input sanitization** beyond prompt injection (tool name validation, description length limits)

### Developer Experience

- **OpenAPI client generation** for frontend teams (auto-generated TypeScript/Python SDKs)
- **Seed data command** for local development (`uv run poe seed`)
- **Structured JSON logging** for production (current coloredlogs for dev, JSON for prod/k8s)
- **Alembic migration linting** in CI to catch common migration pitfalls

---

## Tech Stack

| Technology | Version | Purpose | Why This Choice |
|-----------|---------|---------|----------------|
| **Python** | 3.12+ | Runtime | Modern async support, type hints, performance improvements |
| **FastAPI** | 0.115+ | Web framework | Native async, auto OpenAPI docs, dependency injection |
| **SQLAlchemy** | 2.0 async | ORM | Industry standard, full async support, excellent migration story |
| **PostgreSQL** | 16 | Database | RLS support, JSON operators, battle-tested for multi-tenant |
| **asyncpg** | 0.29+ | DB driver | Fastest PostgreSQL driver for Python async |
| **Alembic** | 1.13+ | Migrations | SQLAlchemy-native, autogenerate, version control |
| **Pydantic** | v2 | Validation | Type-safe, fast, auto-serialization with aliases |
| **dependency-injector** | 4.41+ | DI container | Declarative, supports singletons + resources lifecycle |
| **uv** | latest | Package manager | 10-100x faster than pip, lockfile-based, reproducible |
| **Ruff** | latest | Linter + formatter | Replaces flake8 + black + isort, extremely fast |
| **ty** | latest | Type checker | Lightweight static analysis for Python |
| **pytest** | latest | Testing | Fixtures, parametrize, async support, coverage |
| **Docker** | multi-stage | Containerization | Minimal production images, reproducible builds |
| **GitHub Actions** | - | CI/CD | Native PostgreSQL service containers, uv caching |

---

## License

MIT
