"""Unit tests for ToolService with mocked repository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.data_models.pagination import encode_cursor
from agent_platform.data_models.tool import ToolCreate, ToolResponse, ToolUpdate
from agent_platform.db.models.tool import Tool
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.exceptions import ToolAlreadyExistsError, ToolNotFoundError
from agent_platform.services.tool_service import ToolService


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock(spec=ToolRepository)


@pytest.fixture()
def service(repo: AsyncMock) -> ToolService:
    return ToolService(repo)


def _make_tool(
    tool_id: str = "t1",
    tenant_id: str = "tenant_1",
    name: str = "web-search",
    description: str | None = "Search the web",
) -> MagicMock:
    tool = MagicMock(spec=Tool)
    tool.id = tool_id
    tool.tenant_id = tenant_id
    tool.name = name
    tool.description = description
    tool.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    tool.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return tool


# ---------------------------------------------------------------------------
# create_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tool(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_name.return_value = None
    repo.create.return_value = _make_tool()

    result = await service.create_tool("tenant_1", ToolCreate(name="web-search"))

    assert isinstance(result, ToolResponse)
    assert result.name == "web-search"
    repo.get_by_name.assert_awaited_once_with("tenant_1", "web-search")
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_tool_duplicate(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_name.return_value = _make_tool()

    with pytest.raises(ToolAlreadyExistsError):
        await service.create_tool("tenant_1", ToolCreate(name="web-search"))


# ---------------------------------------------------------------------------
# get_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tool(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = _make_tool()

    result = await service.get_tool("tenant_1", "t1")

    assert result.id == "t1"


@pytest.mark.asyncio
async def test_get_tool_not_found(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(ToolNotFoundError):
        await service.get_tool("tenant_1", "missing")


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_empty(service: ToolService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    result = await service.list_tools("tenant_1")

    assert result.items == []
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_list_tools_with_results(service: ToolService, repo: AsyncMock) -> None:
    expected_count = 2
    tools = [_make_tool("t1"), _make_tool("t2")]
    repo.list_paginated.return_value = (tools, True)

    result = await service.list_tools("tenant_1", limit=expected_count)

    assert len(result.items) == expected_count
    assert result.has_more is True
    assert result.next_cursor is not None


@pytest.mark.asyncio
async def test_list_tools_with_cursor(service: ToolService, repo: AsyncMock) -> None:
    """Passing a cursor string decodes it and forwards to repo."""
    repo.list_paginated.return_value = ([], False)

    cursor = encode_cursor(datetime(2026, 1, 1, tzinfo=UTC), "t1")
    await service.list_tools("tenant_1", cursor=cursor)

    repo.list_paginated.assert_awaited_once()
    call_kwargs = repo.list_paginated.call_args.kwargs
    assert call_kwargs["cursor"] is not None
    assert call_kwargs["cursor"].id == "t1"


# ---------------------------------------------------------------------------
# update_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tool_name(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool()
    repo.get_by_id.return_value = tool
    repo.get_by_name.return_value = None
    repo.update.return_value = tool

    result = await service.update_tool("tenant_1", "t1", ToolUpdate(name="renamed"))

    assert isinstance(result, ToolResponse)
    repo.get_by_name.assert_awaited_once_with("tenant_1", "renamed")


@pytest.mark.asyncio
async def test_update_tool_description(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(description="new desc"))

    # No name uniqueness check when name not changed
    repo.get_by_name.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tool_not_found(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(ToolNotFoundError):
        await service.update_tool("tenant_1", "missing", ToolUpdate(name="x"))


@pytest.mark.asyncio
async def test_update_tool_same_name(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool(name="unchanged")
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(name="unchanged"))

    # Same name should not trigger uniqueness check
    repo.get_by_name.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tool_clear_description(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool(description="old desc")
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(description=None))

    assert tool.description is None


@pytest.mark.asyncio
async def test_update_tool_empty_body(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    result = await service.update_tool("tenant_1", "t1", ToolUpdate())

    repo.get_by_name.assert_not_awaited()
    assert isinstance(result, ToolResponse)


@pytest.mark.asyncio
async def test_update_tool_duplicate_name(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool(name="old-name")
    repo.get_by_id.return_value = tool
    repo.get_by_name.return_value = _make_tool(tool_id="other", name="taken")

    with pytest.raises(ToolAlreadyExistsError):
        await service.update_tool("tenant_1", "t1", ToolUpdate(name="taken"))


# ---------------------------------------------------------------------------
# delete_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_tool(service: ToolService, repo: AsyncMock) -> None:
    tool = _make_tool()
    repo.get_by_id.return_value = tool

    await service.delete_tool("tenant_1", "t1")

    repo.delete.assert_awaited_once_with(tool)


@pytest.mark.asyncio
async def test_delete_tool_not_found(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(ToolNotFoundError):
        await service.delete_tool("tenant_1", "missing")
