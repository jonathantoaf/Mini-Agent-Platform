import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from agent_platform.data_models.pagination import encode_cursor
from agent_platform.data_models.tool import ToolCreate, ToolResponse, ToolUpdate
from agent_platform.db.models.tool import Tool
from agent_platform.exceptions import InvalidCursorError, ToolAlreadyExistsError, ToolNotFoundError
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.tool_service import ToolService
from tests.services.conftest import make_tool


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock(spec=ToolRepository)


@pytest.fixture()
def service(repo: AsyncMock) -> ToolService:
    return ToolService(repo)


# ---------------------------------------------------------------------------
# create_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tool(service: ToolService, repo: AsyncMock) -> None:
    repo.create.return_value = make_tool()

    result = await service.create_tool("tenant_1", ToolCreate(name="web-search"))

    assert isinstance(result, ToolResponse)
    assert result.name == "web-search"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_tool_passes_tenant_id(service: ToolService, repo: AsyncMock) -> None:
    repo.create.return_value = make_tool()

    await service.create_tool("tenant_1", ToolCreate(name="web-search", description="Search"))

    created_tool = repo.create.call_args[0][0]
    assert isinstance(created_tool, Tool)
    assert created_tool.tenant_id == "tenant_1"
    assert created_tool.name == "web-search"
    assert created_tool.description == "Search"


@pytest.mark.asyncio
async def test_create_tool_logs_info(
    service: ToolService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    repo.create.return_value = make_tool()

    caplog.set_level(logging.INFO)

    await service.create_tool("tenant_1", ToolCreate(name="web-search"))

    assert any(
        record.levelno == logging.INFO
        and record.getMessage() == "Created tool tenant_id=tenant_1 tool_id=t1 name=web-search"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_create_tool_duplicate(service: ToolService, repo: AsyncMock) -> None:
    repo.create.side_effect = IntegrityError("", params=None, orig=Exception())

    with pytest.raises(ToolAlreadyExistsError):
        await service.create_tool("tenant_1", ToolCreate(name="web-search"))


# ---------------------------------------------------------------------------
# get_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tool(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = make_tool()

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
    tools = [make_tool("t1"), make_tool("t2")]
    repo.list_paginated.return_value = (tools, True)

    result = await service.list_tools("tenant_1", limit=expected_count)

    assert len(result.items) == expected_count
    assert result.has_more is True
    assert result.next_cursor is not None


@pytest.mark.asyncio
async def test_list_tools_with_cursor(service: ToolService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    cursor = encode_cursor(datetime(2026, 1, 1, tzinfo=UTC), "t1")
    await service.list_tools("tenant_1", cursor=cursor)

    repo.list_paginated.assert_awaited_once()
    call_kwargs = repo.list_paginated.call_args.kwargs
    assert call_kwargs["cursor"] is not None
    assert call_kwargs["cursor"].id == "t1"


@pytest.mark.asyncio
async def test_list_tools_with_agent_name(service: ToolService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    await service.list_tools("tenant_1", agent_name="my-agent")

    call_kwargs = repo.list_paginated.call_args.kwargs
    assert call_kwargs["agent_name"] == "my-agent"


@pytest.mark.asyncio
async def test_list_tools_with_invalid_cursor(service: ToolService) -> None:
    with pytest.raises(InvalidCursorError):
        await service.list_tools("tenant_1", cursor="not-valid-base64!!")


# ---------------------------------------------------------------------------
# update_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tool_name(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    result = await service.update_tool("tenant_1", "t1", ToolUpdate(name="renamed"))

    assert isinstance(result, ToolResponse)
    assert tool.name == "renamed"


@pytest.mark.asyncio
async def test_update_tool_description(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(description="new desc"))

    assert tool.description == "new desc"


@pytest.mark.asyncio
async def test_update_tool_not_found(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(ToolNotFoundError):
        await service.update_tool("tenant_1", "missing", ToolUpdate(name="x"))


@pytest.mark.asyncio
async def test_update_tool_clear_description(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool(description="old desc")
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(description=None))

    assert tool.description is None


@pytest.mark.asyncio
async def test_update_tool_empty_body(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    result = await service.update_tool("tenant_1", "t1", ToolUpdate())

    assert isinstance(result, ToolResponse)


@pytest.mark.asyncio
async def test_update_tool_null_name_ignored(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool(name="original")
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    await service.update_tool("tenant_1", "t1", ToolUpdate(name=None))

    assert tool.name == "original"


@pytest.mark.asyncio
async def test_update_tool_duplicate_name(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool(name="old-name")
    repo.get_by_id.return_value = tool
    repo.update.side_effect = IntegrityError("", params=None, orig=Exception())

    with pytest.raises(ToolAlreadyExistsError):
        await service.update_tool("tenant_1", "t1", ToolUpdate(name="taken"))


@pytest.mark.asyncio
async def test_update_tool_logs_info(
    service: ToolService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    tool = make_tool()
    repo.get_by_id.return_value = tool
    repo.update.return_value = tool

    caplog.set_level(logging.INFO)

    await service.update_tool("tenant_1", "t1", ToolUpdate(name="renamed"))

    assert any(
        record.levelno == logging.INFO
        and record.getMessage() == "Updated tool tenant_id=tenant_1 tool_id=t1 name=renamed"
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# delete_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_tool(service: ToolService, repo: AsyncMock) -> None:
    tool = make_tool()
    repo.get_by_id.return_value = tool

    await service.delete_tool("tenant_1", "t1")

    repo.delete.assert_awaited_once_with(tool)


@pytest.mark.asyncio
async def test_delete_tool_logs_info(
    service: ToolService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    repo.get_by_id.return_value = make_tool()

    caplog.set_level(logging.INFO)

    await service.delete_tool("tenant_1", "t1")

    assert any(
        record.levelno == logging.INFO
        and record.getMessage() == "Deleted tool tenant_id=tenant_1 tool_id=t1"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_delete_tool_not_found(service: ToolService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(ToolNotFoundError):
        await service.delete_tool("tenant_1", "missing")
