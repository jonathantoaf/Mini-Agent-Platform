import logging

from agent_platform.data_models.execution import ExecutionResponse
from agent_platform.data_models.pagination import (
    CursorData,
    PaginatedResponse,
    decode_cursor,
    encode_cursor,
)
from agent_platform.data_models.run import ChatMessage, ToolCallRecord
from agent_platform.db.models.execution import Execution
from agent_platform.exceptions import AgentNotFoundError, ExecutionNotFoundError
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.execution_repository import ExecutionRepository
from agent_platform.settings import get_settings


class ExecutionService:
    def __init__(self, execution_repo: ExecutionRepository, agent_repo: AgentRepository) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._execution_repo = execution_repo
        self._agent_repo = agent_repo

    async def get_execution(self, tenant_id: str, execution_id: str) -> ExecutionResponse:
        self._logger.debug(f"Fetching execution tenant_id={tenant_id} execution_id={execution_id}")
        execution = await self._execution_repo.get_by_id(tenant_id, execution_id)
        if not execution:
            self._logger.warning(
                f"Execution not found tenant_id={tenant_id} execution_id={execution_id}"
            )
            raise ExecutionNotFoundError
        return self._to_response(execution)

    async def list_executions(
        self,
        tenant_id: str,
        agent_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: str | None = None,
    ) -> PaginatedResponse[ExecutionResponse]:
        self._logger.debug(
            f"Listing executions tenant_id={tenant_id} agent_id={agent_id} "
            f"limit={limit} cursor={cursor}"
        )

        agent = await self._agent_repo.get_by_id(tenant_id, agent_id)
        if not agent:
            self._logger.warning(f"Agent not found tenant_id={tenant_id} agent_id={agent_id}")
            raise AgentNotFoundError

        cursor_data: CursorData | None = None
        if cursor:
            cursor_data = decode_cursor(cursor)

        executions, has_more = await self._execution_repo.list_paginated(
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=limit,
            cursor=cursor_data,
        )

        next_cursor: str | None = None
        if has_more and executions:
            last = executions[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return PaginatedResponse[ExecutionResponse](
            items=[self._to_response(e) for e in executions],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    @staticmethod
    def _to_response(execution: Execution) -> ExecutionResponse:
        return ExecutionResponse(
            execution_id=execution.id,
            agent_id=execution.agent_id,
            task=execution.task,
            model=execution.model,
            final_response=execution.final_response,
            tool_calls=[ToolCallRecord(**tc) for tc in execution.tool_calls],
            messages=[ChatMessage(**msg) for msg in execution.messages],
            created_at=execution.created_at,
        )
