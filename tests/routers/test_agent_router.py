"""Unit tests for the Agent router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import get_agent_service
from agent_platform.api.routers.agent_router import router
from agent_platform.data_models.agent import AgentResponse
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.data_models.tool import ToolResponse
from agent_platform.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    InvalidCursorError,
    ToolNotFoundError,
)
from tests.routers.conftest import TENANT_ID, make_test_client

AGENTS_URL = "/api/v1/agents"
_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_tool_response(**overrides: object) -> ToolResponse:
    defaults = {
        "id": "t1",
        "name": "web-search",
        "description": "Search the web",
        "created_at": _CREATED_AT,
        "updated_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return ToolResponse(**defaults)


def _make_response(**overrides: object) -> AgentResponse:
    defaults: dict = {
        "id": "a1",
        "name": "my-agent",
        "role": "assistant",
        "description": "An agent",
        "tools": [],
        "created_at": _CREATED_AT,
        "updated_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return AgentResponse(**defaults)


@pytest.fixture()
def client(mock_service: AsyncMock) -> TestClient:
    return make_test_client(router, (get_agent_service, mock_service))


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateAgent:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_agent.return_value = _make_response()

        resp = client.post(
            AGENTS_URL,
            json={"name": "my-agent", "role": "assistant", "description": "An agent"},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["name"] == "my-agent"
        assert body["role"] == "assistant"
        assert body["description"] == "An agent"
        assert body["tools"] == []
        assert "id" in body
        assert "createdAt" in body
        assert "updatedAt" in body
        assert "tenantId" not in body
        assert "tenant_id" not in body

    def test_success_with_tools(self, client: TestClient, mock_service: AsyncMock) -> None:
        tool = _make_tool_response()
        mock_service.create_agent.return_value = _make_response(tools=[tool])

        resp = client.post(
            AGENTS_URL,
            json={"name": "tooled-agent", "role": "assistant", "toolIds": ["t1"]},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["tools"]) == 1
        assert resp.json()["tools"][0]["id"] == "t1"

    def test_duplicate_name_returns_409(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_agent.side_effect = AgentAlreadyExistsError

        resp = client.post(AGENTS_URL, json={"name": "dup", "role": "assistant"})

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_invalid_tool_ids_returns_404(
        self, client: TestClient, mock_service: AsyncMock
    ) -> None:
        mock_service.create_agent.side_effect = ToolNotFoundError

        resp = client.post(
            AGENTS_URL,
            json={"name": "agent", "role": "assistant", "toolIds": ["nonexistent"]},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_passes_correct_args(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_agent.return_value = _make_response()

        client.post(
            AGENTS_URL,
            json={"name": "test", "role": "researcher", "description": "desc"},
        )

        mock_service.create_agent.assert_awaited_once()
        args = mock_service.create_agent.call_args[0]
        assert args[0] == TENANT_ID
        assert args[1].name == "test"
        assert args[1].role == "researcher"
        assert args[1].description == "desc"

    @pytest.mark.parametrize(
        "payload",
        [
            {"role": "assistant"},
            {"name": "x"},
            {"name": "", "role": "assistant"},
            {"name": "x" * 256, "role": "assistant"},
        ],
        ids=["missing-name", "missing-role", "empty-name", "name-too-long"],
    )
    def test_validation_error(
        self, client: TestClient, mock_service: AsyncMock, payload: dict
    ) -> None:
        resp = client.post(AGENTS_URL, json=payload)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_service.create_agent.assert_not_awaited()


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGetAgent:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_agent.return_value = _make_response()

        resp = client.get(f"{AGENTS_URL}/a1")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == "a1"
        assert resp.json()["name"] == "my-agent"

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_agent.side_effect = AgentNotFoundError

        resp = client.get(f"{AGENTS_URL}/missing")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"] == "Agent not found."

    def test_passes_tenant_id(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_agent.return_value = _make_response()

        client.get(f"{AGENTS_URL}/a1")

        mock_service.get_agent.assert_awaited_once_with(TENANT_ID, "a1")


# ---------------------------------------------------------------------------
# List + Pagination
# ---------------------------------------------------------------------------


class TestListAgents:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.return_value = PaginatedResponse[AgentResponse](
            items=[_make_response()],
            has_more=False,
            next_cursor=None,
        )

        resp = client.get(AGENTS_URL)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["hasMore"] is False

    def test_empty(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.return_value = PaginatedResponse[AgentResponse](
            items=[], has_more=False, next_cursor=None
        )

        resp = client.get(AGENTS_URL)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["items"] == []

    def test_pagination_params(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.return_value = PaginatedResponse[AgentResponse](
            items=[], has_more=False, next_cursor=None
        )

        client.get(f"{AGENTS_URL}?cursor=abc123&limit=5")

        mock_service.list_agents.assert_awaited_once()
        kwargs = mock_service.list_agents.call_args.kwargs
        assert kwargs["cursor"] == "abc123"
        assert kwargs["limit"] == 5

    def test_invalid_cursor(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.side_effect = InvalidCursorError

        resp = client.get(f"{AGENTS_URL}?cursor=bad")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "Invalid pagination cursor."

    def test_tool_name_filter(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.return_value = PaginatedResponse[AgentResponse](
            items=[], has_more=False, next_cursor=None
        )

        client.get(f"{AGENTS_URL}?tool_name=web-search")

        kwargs = mock_service.list_agents.call_args.kwargs
        assert kwargs["tool_name"] == "web-search"

    def test_has_more_with_cursor(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_agents.return_value = PaginatedResponse[AgentResponse](
            items=[_make_response()], has_more=True, next_cursor="next_page"
        )

        resp = client.get(AGENTS_URL)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["hasMore"] is True
        assert resp.json()["nextCursor"] == "next_page"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateAgent:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_agent.return_value = _make_response(name="renamed")

        resp = client.patch(f"{AGENTS_URL}/a1", json={"name": "renamed"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "renamed"

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_agent.side_effect = AgentNotFoundError

        resp = client.patch(f"{AGENTS_URL}/missing", json={"name": "x"})

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_duplicate_name(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_agent.side_effect = AgentAlreadyExistsError

        resp = client.patch(f"{AGENTS_URL}/a1", json={"name": "taken"})

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_invalid_tool_ids(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_agent.side_effect = ToolNotFoundError

        resp = client.patch(f"{AGENTS_URL}/a1", json={"toolIds": ["nonexistent"]})

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_passes_correct_args(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_agent.return_value = _make_response()

        client.patch(f"{AGENTS_URL}/a1", json={"name": "new-name", "role": "researcher"})

        mock_service.update_agent.assert_awaited_once()
        args = mock_service.update_agent.call_args[0]
        assert args[0] == TENANT_ID
        assert args[1] == "a1"
        assert args[2].name == "new-name"
        assert args[2].role == "researcher"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteAgent:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        resp = client.delete(f"{AGENTS_URL}/a1")

        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_service.delete_agent.assert_awaited_once_with(TENANT_ID, "a1")

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.delete_agent.side_effect = AgentNotFoundError

        resp = client.delete(f"{AGENTS_URL}/missing")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
