import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from agent_platform.data_models.agent import AgentCreate, AgentResponse, AgentUpdate
from agent_platform.data_models.pagination import encode_cursor
from agent_platform.db.models.agent import Agent
from agent_platform.db.models.tool import Tool
from agent_platform.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ToolNotFoundError,
)
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.agent_service import AgentService


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock(spec=AgentRepository)


@pytest.fixture()
def tool_repo() -> AsyncMock:
    return AsyncMock(spec=ToolRepository)


@pytest.fixture()
def service(repo: AsyncMock, tool_repo: AsyncMock) -> AgentService:
    return AgentService(repo, tool_repo)


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


def _make_agent(
    agent_id: str = "a1",
    tenant_id: str = "tenant_1",
    name: str = "my-agent",
    role: str = "assistant",
    description: str | None = "An agent",
    tools: list[MagicMock] | None = None,
) -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.id = agent_id
    agent.tenant_id = tenant_id
    agent.name = name
    agent.role = role
    agent.description = description
    agent.tools = tools or []
    agent.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    agent.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return agent


# ---------------------------------------------------------------------------
# create_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_agent_no_tools(
    service: AgentService, repo: AsyncMock, tool_repo: AsyncMock
) -> None:
    repo.create.return_value = _make_agent()

    result = await service.create_agent("tenant_1", AgentCreate(name="my-agent", role="assistant"))

    assert isinstance(result, AgentResponse)
    assert result.name == "my-agent"
    assert result.role == "assistant"
    assert result.tools == []
    repo.create.assert_awaited_once()
    tool_repo.get_by_ids.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_agent_with_tools(
    service: AgentService, repo: AsyncMock, tool_repo: AsyncMock
) -> None:
    tool = _make_tool()
    tool_repo.get_by_ids.return_value = [tool]
    repo.create.return_value = _make_agent(tools=[tool])

    result = await service.create_agent(
        "tenant_1", AgentCreate(name="my-agent", role="assistant", tool_ids=["t1"])
    )

    assert len(result.tools) == 1
    assert result.tools[0].id == "t1"


@pytest.mark.asyncio
async def test_create_agent_invalid_tool_ids(service: AgentService, tool_repo: AsyncMock) -> None:
    tool_repo.get_by_ids.return_value = []

    with pytest.raises(ToolNotFoundError):
        await service.create_agent(
            "tenant_1", AgentCreate(name="my-agent", role="assistant", tool_ids=["nonexistent"])
        )


@pytest.mark.asyncio
async def test_create_agent_duplicate(service: AgentService, repo: AsyncMock) -> None:
    repo.create.side_effect = IntegrityError("", params=None, orig=Exception())

    with pytest.raises(AgentAlreadyExistsError):
        await service.create_agent("tenant_1", AgentCreate(name="my-agent", role="assistant"))


@pytest.mark.asyncio
async def test_create_agent_logs_info(
    service: AgentService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    repo.create.return_value = _make_agent()

    caplog.set_level(logging.INFO)

    await service.create_agent("tenant_1", AgentCreate(name="my-agent", role="assistant"))

    assert any(
        record.levelno == logging.INFO
        and record.getMessage()
        == "Created agent tenant_id=tenant_1 agent_id=a1 name=my-agent tool_count=0"
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# get_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_agent(service: AgentService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = _make_agent()

    result = await service.get_agent("tenant_1", "a1")

    assert result.id == "a1"


@pytest.mark.asyncio
async def test_get_agent_not_found(service: AgentService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(AgentNotFoundError):
        await service.get_agent("tenant_1", "missing")


# ---------------------------------------------------------------------------
# list_agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_agents_empty(service: AgentService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    result = await service.list_agents("tenant_1")

    assert result.items == []
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_list_agents_with_results(service: AgentService, repo: AsyncMock) -> None:
    expected_count = 2
    agents = [_make_agent("a1"), _make_agent("a2")]
    repo.list_paginated.return_value = (agents, True)

    result = await service.list_agents("tenant_1", limit=expected_count)

    assert len(result.items) == expected_count
    assert result.has_more is True
    assert result.next_cursor is not None


@pytest.mark.asyncio
async def test_list_agents_with_cursor(service: AgentService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    cursor = encode_cursor(datetime(2026, 1, 1, tzinfo=UTC), "a1")
    await service.list_agents("tenant_1", cursor=cursor)

    repo.list_paginated.assert_awaited_once()
    call_kwargs = repo.list_paginated.call_args.kwargs
    assert call_kwargs["cursor"] is not None
    assert call_kwargs["cursor"].id == "a1"


@pytest.mark.asyncio
async def test_list_agents_with_tool_name(service: AgentService, repo: AsyncMock) -> None:
    repo.list_paginated.return_value = ([], False)

    await service.list_agents("tenant_1", tool_name="web-search")

    call_kwargs = repo.list_paginated.call_args.kwargs
    assert call_kwargs["tool_name"] == "web-search"


# ---------------------------------------------------------------------------
# update_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_agent_name(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    result = await service.update_agent("tenant_1", "a1", AgentUpdate(name="renamed"))

    assert isinstance(result, AgentResponse)
    assert agent.name == "renamed"


@pytest.mark.asyncio
async def test_update_agent_role(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(role="new-role"))

    assert agent.role == "new-role"


@pytest.mark.asyncio
async def test_update_agent_description(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(description="new desc"))

    assert agent.description == "new desc"


@pytest.mark.asyncio
async def test_update_agent_clear_description(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent(description="old desc")
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(description=None))

    assert agent.description is None


@pytest.mark.asyncio
async def test_update_agent_tools(
    service: AgentService, repo: AsyncMock, tool_repo: AsyncMock
) -> None:
    tool = _make_tool()
    tool_repo.get_by_ids.return_value = [tool]
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(tool_ids=["t1"]))

    assert agent.tools == [tool]


@pytest.mark.asyncio
async def test_update_agent_clear_tools(
    service: AgentService, repo: AsyncMock, tool_repo: AsyncMock
) -> None:
    agent = _make_agent(tools=[_make_tool()])
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(tool_ids=[]))

    assert agent.tools == []
    tool_repo.get_by_ids.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_agent_empty_body(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    result = await service.update_agent("tenant_1", "a1", AgentUpdate())

    assert isinstance(result, AgentResponse)


@pytest.mark.asyncio
async def test_update_agent_null_name_ignored(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent(name="original")
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    await service.update_agent("tenant_1", "a1", AgentUpdate(name=None))

    assert agent.name == "original"


@pytest.mark.asyncio
async def test_update_agent_not_found(service: AgentService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(AgentNotFoundError):
        await service.update_agent("tenant_1", "missing", AgentUpdate(name="x"))


@pytest.mark.asyncio
async def test_update_agent_duplicate_name(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent(name="old-name")
    repo.get_by_id.return_value = agent
    repo.update.side_effect = IntegrityError("", params=None, orig=Exception())

    with pytest.raises(AgentAlreadyExistsError):
        await service.update_agent("tenant_1", "a1", AgentUpdate(name="taken"))


@pytest.mark.asyncio
async def test_update_agent_invalid_tool_ids(
    service: AgentService, repo: AsyncMock, tool_repo: AsyncMock
) -> None:
    tool_repo.get_by_ids.return_value = []
    agent = _make_agent()
    repo.get_by_id.return_value = agent

    with pytest.raises(ToolNotFoundError):
        await service.update_agent("tenant_1", "a1", AgentUpdate(tool_ids=["nonexistent"]))


@pytest.mark.asyncio
async def test_update_agent_logs_info(
    service: AgentService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent
    repo.update.return_value = agent

    caplog.set_level(logging.INFO)

    await service.update_agent("tenant_1", "a1", AgentUpdate(name="renamed"))

    assert any(
        record.levelno == logging.INFO
        and record.getMessage()
        == "Updated agent tenant_id=tenant_1 agent_id=a1 name=renamed tool_count=0"
        for record in caplog.records
    )


# ---------------------------------------------------------------------------
# delete_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_agent(service: AgentService, repo: AsyncMock) -> None:
    agent = _make_agent()
    repo.get_by_id.return_value = agent

    await service.delete_agent("tenant_1", "a1")

    repo.delete.assert_awaited_once_with(agent)


@pytest.mark.asyncio
async def test_delete_agent_logs_info(
    service: AgentService, repo: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    repo.get_by_id.return_value = _make_agent()

    caplog.set_level(logging.INFO)

    await service.delete_agent("tenant_1", "a1")

    assert any(
        record.levelno == logging.INFO
        and record.getMessage() == "Deleted agent tenant_id=tenant_1 agent_id=a1"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_delete_agent_not_found(service: AgentService, repo: AsyncMock) -> None:
    repo.get_by_id.return_value = None

    with pytest.raises(AgentNotFoundError):
        await service.delete_agent("tenant_1", "missing")
