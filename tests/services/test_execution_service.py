from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.data_models.execution import ExecutionResponse
from agent_platform.data_models.pagination import PaginatedResponse, encode_cursor
from agent_platform.db.models.agent import Agent
from agent_platform.db.models.execution import Execution
from agent_platform.exceptions import AgentNotFoundError, ExecutionNotFoundError
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.execution_repository import ExecutionRepository
from agent_platform.services.execution_service import ExecutionService

_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_execution(
    execution_id: str = "exec-1",
    tenant_id: str = "tenant_1",
    agent_id: str = "agent-1",
    task: str = "Say hello",
    model: str = "gpt-4o",
    final_response: str = "Hello!",
    tool_calls: list | None = None,
    messages: list | None = None,
) -> MagicMock:
    execution = MagicMock(spec=Execution)
    execution.id = execution_id
    execution.tenant_id = tenant_id
    execution.agent_id = agent_id
    execution.task = task
    execution.model = model
    execution.final_response = final_response
    execution.tool_calls = tool_calls or []
    execution.messages = (
        [{"role": "user", "content": "Say hello"}] if messages is None else messages
    )
    execution.created_at = _CREATED_AT
    return execution


@pytest.fixture()
def execution_repo() -> AsyncMock:
    return AsyncMock(spec=ExecutionRepository)


@pytest.fixture()
def agent_repo() -> AsyncMock:
    return AsyncMock(spec=AgentRepository)


@pytest.fixture()
def service(execution_repo: AsyncMock, agent_repo: AsyncMock) -> ExecutionService:
    return ExecutionService(execution_repo, agent_repo)


# ---------------------------------------------------------------------------
# get_execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_execution_success(service: ExecutionService, execution_repo: AsyncMock) -> None:
    execution_repo.get_by_id.return_value = _make_execution()

    result = await service.get_execution("tenant_1", "exec-1")

    assert isinstance(result, ExecutionResponse)
    assert result.execution_id == "exec-1"
    assert result.agent_id == "agent-1"
    assert result.final_response == "Hello!"
    execution_repo.get_by_id.assert_awaited_once_with("tenant_1", "exec-1")


@pytest.mark.asyncio
async def test_get_execution_not_found(
    service: ExecutionService, execution_repo: AsyncMock
) -> None:
    execution_repo.get_by_id.return_value = None

    with pytest.raises(ExecutionNotFoundError):
        await service.get_execution("tenant_1", "missing")


@pytest.mark.asyncio
async def test_get_execution_includes_messages_and_tool_calls(
    service: ExecutionService, execution_repo: AsyncMock
) -> None:
    execution_repo.get_by_id.return_value = _make_execution(
        messages=[{"role": "user", "content": "hello"}],
        tool_calls=[
            {
                "tool_call_id": "call_1",
                "tool_name": "web-search",
                "arguments": '{"q": "test"}',
                "result": "found it",
            }
        ],
    )

    result = await service.get_execution("tenant_1", "exec-1")

    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "web-search"


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_executions_success(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    execution_repo.list_paginated.return_value = ([_make_execution()], False)

    result = await service.list_executions("tenant_1", "agent-1")

    assert isinstance(result, PaginatedResponse)
    assert len(result.items) == 1
    assert isinstance(result.items[0], ExecutionResponse)
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_list_executions_agent_not_found(
    service: ExecutionService, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = None

    with pytest.raises(AgentNotFoundError):
        await service.list_executions("tenant_1", "missing-agent")


@pytest.mark.asyncio
async def test_list_executions_empty(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    execution_repo.list_paginated.return_value = ([], False)

    result = await service.list_executions("tenant_1", "agent-1")

    assert result.items == []
    assert result.has_more is False
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_list_executions_has_more(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    executions = [_make_execution("e1"), _make_execution("e2")]
    execution_repo.list_paginated.return_value = (executions, True)

    result = await service.list_executions("tenant_1", "agent-1", limit=2)

    assert len(result.items) == 2
    assert result.has_more is True
    assert result.next_cursor is not None


@pytest.mark.asyncio
async def test_list_executions_with_cursor(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    execution_repo.list_paginated.return_value = ([], False)

    cursor = encode_cursor(_CREATED_AT, "e1")
    await service.list_executions("tenant_1", "agent-1", cursor=cursor)

    execution_repo.list_paginated.assert_awaited_once()
    call_kwargs = execution_repo.list_paginated.call_args.kwargs
    assert call_kwargs["cursor"] is not None
    assert call_kwargs["cursor"].id == "e1"


@pytest.mark.asyncio
async def test_list_executions_passes_agent_id_to_repo(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    execution_repo.list_paginated.return_value = ([], False)

    await service.list_executions("tenant_1", "agent-1")

    call_kwargs = execution_repo.list_paginated.call_args.kwargs
    assert call_kwargs["agent_id"] == "agent-1"
    assert call_kwargs["tenant_id"] == "tenant_1"


@pytest.mark.asyncio
async def test_list_executions_with_invalid_cursor(
    service: ExecutionService, execution_repo: AsyncMock, agent_repo: AsyncMock
) -> None:
    """Invalid cursor string should be treated as None (start from beginning)."""
    agent_repo.get_by_id.return_value = MagicMock(spec=Agent)
    execution_repo.list_paginated.return_value = ([], False)

    await service.list_executions("tenant_1", "agent-1", cursor="not-valid-base64!!")

    call_kwargs = execution_repo.list_paginated.call_args.kwargs
    assert call_kwargs["cursor"] is None


@pytest.mark.asyncio
async def test_get_execution_multiple_tool_calls(
    service: ExecutionService, execution_repo: AsyncMock
) -> None:
    """Verify correct conversion when execution has multiple tool calls."""
    execution_repo.get_by_id.return_value = _make_execution(
        tool_calls=[
            {
                "tool_call_id": "call_1",
                "tool_name": "web-search",
                "arguments": '{"q": "test"}',
                "result": "found it",
            },
            {
                "tool_call_id": "call_2",
                "tool_name": "calculator",
                "arguments": '{"expr": "2+2"}',
                "result": "4",
            },
            {
                "tool_call_id": "call_3",
                "tool_name": "file-reader",
                "arguments": '{"path": "/tmp/x"}',
                "result": "contents",
            },
        ],
    )

    result = await service.get_execution("tenant_1", "exec-1")

    assert len(result.tool_calls) == 3
    assert result.tool_calls[0].tool_name == "web-search"
    assert result.tool_calls[1].tool_name == "calculator"
    assert result.tool_calls[2].tool_name == "file-reader"


@pytest.mark.asyncio
async def test_get_execution_empty_messages(
    service: ExecutionService, execution_repo: AsyncMock
) -> None:
    """Edge case: execution with empty messages array."""
    execution_repo.get_by_id.return_value = _make_execution(messages=[])

    result = await service.get_execution("tenant_1", "exec-1")

    assert result.messages == []
