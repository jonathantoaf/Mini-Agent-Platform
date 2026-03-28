"""Unit tests for the Tool router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import get_tool_service
from agent_platform.api.routers.tool_router import router
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.data_models.tool import ToolResponse
from agent_platform.exceptions import InvalidCursorError, ToolAlreadyExistsError, ToolNotFoundError
from tests.routers.conftest import TENANT_ID, make_test_client

BASE_URL = "/api/v1/tools"
_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_response(**overrides: object) -> ToolResponse:
    defaults = {
        "id": "t1",
        "name": "web-search",
        "description": "Search the web",
        "created_at": _CREATED_AT,
        "updated_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return ToolResponse(**defaults)


@pytest.fixture()
def client(mock_service: AsyncMock) -> TestClient:
    return make_test_client(router, (get_tool_service, mock_service))


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateTool:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_tool.return_value = _make_response()

        resp = client.post(
            BASE_URL,
            json={"name": "web-search", "description": "Search the web"},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["name"] == "web-search"
        assert body["description"] == "Search the web"
        assert "id" in body
        assert "createdAt" in body
        assert "updatedAt" in body
        assert "tenantId" not in body
        assert "tenant_id" not in body

    def test_duplicate_name_returns_409(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_tool.side_effect = ToolAlreadyExistsError

        resp = client.post(BASE_URL, json={"name": "dup-tool"})

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_passes_correct_args(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.create_tool.return_value = _make_response()

        client.post(BASE_URL, json={"name": "my-tool", "description": "desc"})

        mock_service.create_tool.assert_awaited_once()
        args = mock_service.create_tool.call_args[0]
        assert args[0] == TENANT_ID
        assert args[1].name == "my-tool"
        assert args[1].description == "desc"

    @pytest.mark.parametrize(
        "payload",
        [{}, {"name": ""}, {"name": "x" * 256}],
        ids=["missing-name", "empty-name", "name-too-long"],
    )
    def test_validation_error(
        self, client: TestClient, mock_service: AsyncMock, payload: dict
    ) -> None:
        resp = client.post(BASE_URL, json=payload)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_service.create_tool.assert_not_awaited()


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGetTool:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_tool.return_value = _make_response()

        resp = client.get(f"{BASE_URL}/t1")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == "t1"
        assert resp.json()["name"] == "web-search"

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_tool.side_effect = ToolNotFoundError

        resp = client.get(f"{BASE_URL}/missing")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["detail"] == "Tool not found."

    def test_passes_tenant_id(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.get_tool.return_value = _make_response()

        client.get(f"{BASE_URL}/t1")

        mock_service.get_tool.assert_awaited_once_with(TENANT_ID, "t1")


# ---------------------------------------------------------------------------
# List + Pagination
# ---------------------------------------------------------------------------


class TestListTools:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.return_value = PaginatedResponse[ToolResponse](
            items=[_make_response()],
            has_more=False,
            next_cursor=None,
        )

        resp = client.get(BASE_URL)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["hasMore"] is False

    def test_empty(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.return_value = PaginatedResponse[ToolResponse](
            items=[], has_more=False, next_cursor=None
        )

        resp = client.get(BASE_URL)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["items"] == []

    def test_pagination_params(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.return_value = PaginatedResponse[ToolResponse](
            items=[], has_more=False, next_cursor=None
        )

        client.get(f"{BASE_URL}?cursor=abc123&limit=5")

        mock_service.list_tools.assert_awaited_once()
        kwargs = mock_service.list_tools.call_args.kwargs
        assert kwargs["cursor"] == "abc123"
        assert kwargs["limit"] == 5

    def test_invalid_cursor(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.side_effect = InvalidCursorError

        resp = client.get(f"{BASE_URL}?cursor=bad")

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "Invalid pagination cursor."

    def test_agent_name_filter(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.return_value = PaginatedResponse[ToolResponse](
            items=[], has_more=False, next_cursor=None
        )

        client.get(f"{BASE_URL}?agent_name=my-agent")

        kwargs = mock_service.list_tools.call_args.kwargs
        assert kwargs["agent_name"] == "my-agent"

    def test_has_more_with_cursor(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.list_tools.return_value = PaginatedResponse[ToolResponse](
            items=[_make_response()], has_more=True, next_cursor="next_page"
        )

        resp = client.get(BASE_URL)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["hasMore"] is True
        assert resp.json()["nextCursor"] == "next_page"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateTool:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_tool.return_value = _make_response(name="renamed")

        resp = client.patch(f"{BASE_URL}/t1", json={"name": "renamed"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "renamed"

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_tool.side_effect = ToolNotFoundError

        resp = client.patch(f"{BASE_URL}/missing", json={"name": "x"})

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_duplicate_name(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_tool.side_effect = ToolAlreadyExistsError

        resp = client.patch(f"{BASE_URL}/t1", json={"name": "taken"})

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_passes_correct_args(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.update_tool.return_value = _make_response()

        client.patch(f"{BASE_URL}/t1", json={"name": "new-name"})

        mock_service.update_tool.assert_awaited_once()
        args = mock_service.update_tool.call_args[0]
        assert args[0] == TENANT_ID
        assert args[1] == "t1"
        assert args[2].name == "new-name"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteTool:
    def test_success(self, client: TestClient, mock_service: AsyncMock) -> None:
        resp = client.delete(f"{BASE_URL}/t1")

        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_service.delete_tool.assert_awaited_once_with(TENANT_ID, "t1")

    def test_not_found(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.delete_tool.side_effect = ToolNotFoundError

        resp = client.delete(f"{BASE_URL}/missing")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
