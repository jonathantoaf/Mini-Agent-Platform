"""Unit tests for the Execution History router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import get_execution_service
from agent_platform.api.routers.execution_router import agent_executions_router, executions_router
from agent_platform.auth.api_key import get_current_tenant_id
from agent_platform.data_models.execution import ExecutionResponse
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.data_models.run import ChatMessage, ToolCallRecord
from agent_platform.exceptions import AgentNotFoundError, ExecutionNotFoundError

_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_response(**overrides: object) -> ExecutionResponse:
    defaults = {
        "execution_id": "exec-1",
        "agent_id": "agent-1",
        "task": "Say hello",
        "model": "gpt-4o",
        "final_response": "Hello!",
        "tool_calls": [],
        "messages": [ChatMessage(role="user", content="Say hello")],
        "created_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return ExecutionResponse(**defaults)


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(agent_executions_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.dependency_overrides[get_execution_service] = lambda: mock_service
    app.dependency_overrides[get_current_tenant_id] = lambda: "tenant_1"

    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/v1/executions/{execution_id}
# ---------------------------------------------------------------------------


class TestGetExecution:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_execution.return_value = _make_response()

        resp = client.get("/api/v1/executions/exec-1")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["executionId"] == "exec-1"
        assert data["agentId"] == "agent-1"
        assert data["finalResponse"] == "Hello!"
        assert "messages" in data
        assert "toolCalls" in data

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_execution.side_effect = ExecutionNotFoundError

        resp = client.get("/api/v1/executions/missing")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"] == "Execution not found."

    def test_passes_tenant_id(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_execution.return_value = _make_response()

        client.get("/api/v1/executions/exec-1")

        mock_service.get_execution.assert_awaited_once_with("tenant_1", "exec-1")

    def test_tenant_isolation(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_execution.side_effect = ExecutionNotFoundError

        resp = client.get("/api/v1/executions/exec-owned-by-other-tenant")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        mock_service.get_execution.assert_awaited_once_with(
            "tenant_1", "exec-owned-by-other-tenant"
        )

    def test_includes_tool_calls(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_execution.return_value = _make_response(
            tool_calls=[
                ToolCallRecord(
                    tool_call_id="call_1",
                    tool_name="web-search",
                    arguments='{"q": "test"}',
                    result="found it",
                )
            ],
        )

        resp = client.get("/api/v1/executions/exec-1")

        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["toolCalls"]) == 1
        assert resp.json()["toolCalls"][0]["toolName"] == "web-search"


# ---------------------------------------------------------------------------
# GET /api/v1/agents/{agent_id}/executions
# ---------------------------------------------------------------------------


class TestListExecutions:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[_make_response()],
            has_more=False,
            next_cursor=None,
        )

        resp = client.get("/api/v1/agents/agent-1/executions")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["executionId"] == "exec-1"
        assert data["hasMore"] is False
        assert "messages" in data["items"][0]
        assert "toolCalls" in data["items"][0]

    def test_empty(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[],
            has_more=False,
            next_cursor=None,
        )

        resp = client.get("/api/v1/agents/agent-1/executions")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["items"] == []
        assert resp.json()["hasMore"] is False

    def test_agent_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.side_effect = AgentNotFoundError

        resp = client.get("/api/v1/agents/missing/executions")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"] == "Agent not found."

    def test_pagination_params(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[],
            has_more=False,
            next_cursor=None,
        )

        client.get("/api/v1/agents/agent-1/executions?cursor=abc123&limit=5")

        mock_service.list_executions.assert_awaited_once()
        call_kwargs = mock_service.list_executions.call_args.kwargs
        assert call_kwargs["cursor"] == "abc123"
        assert call_kwargs["limit"] == 5

    def test_passes_tenant_and_agent_id(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[],
            has_more=False,
            next_cursor=None,
        )

        client.get("/api/v1/agents/my-agent/executions")

        mock_service.list_executions.assert_awaited_once()
        call_kwargs = mock_service.list_executions.call_args.kwargs
        assert call_kwargs["tenant_id"] == "tenant_1"
        assert call_kwargs["agent_id"] == "my-agent"

    def test_default_limit(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[],
            has_more=False,
            next_cursor=None,
        )

        client.get("/api/v1/agents/agent-1/executions")

        call_kwargs = mock_service.list_executions.call_args.kwargs
        assert call_kwargs["limit"] == 20

    def test_invalid_limit_zero(self, client: TestClient, mock_service: AsyncMock) -> None:
        resp = client.get("/api/v1/agents/agent-1/executions?limit=0")

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_service.list_executions.assert_not_awaited()

    def test_invalid_limit_exceeds_max(self, client: TestClient, mock_service: AsyncMock) -> None:
        resp = client.get("/api/v1/agents/agent-1/executions?limit=999")

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_service.list_executions.assert_not_awaited()

    def test_has_more_with_cursor(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_executions.return_value = PaginatedResponse[ExecutionResponse](
            items=[_make_response()],
            has_more=True,
            next_cursor="next_page_cursor",
        )

        resp = client.get("/api/v1/agents/agent-1/executions")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["hasMore"] is True
        assert data["nextCursor"] == "next_page_cursor"
