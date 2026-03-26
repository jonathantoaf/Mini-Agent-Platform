from sqlalchemy.exc import IntegrityError

from agent_platform.data_models.pagination import (
    CursorData,
    PaginatedResponse,
    decode_cursor,
    encode_cursor,
)
from agent_platform.data_models.tool import ToolCreate, ToolResponse, ToolUpdate
from agent_platform.db.models.tool import Tool
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.exceptions import ToolAlreadyExistsError, ToolNotFoundError


class ToolService:
    def __init__(self, repository: ToolRepository) -> None:
        self._repository = repository

    async def create_tool(self, tenant_id: str, data: ToolCreate) -> ToolResponse:
        tool = Tool(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
        )
        try:
            tool = await self._repository.create(tool)
        except IntegrityError:
            raise ToolAlreadyExistsError from None
        return self._to_response(tool)

    async def get_tool(self, tenant_id: str, tool_id: str) -> ToolResponse:
        tool = await self._repository.get_by_id(tenant_id, tool_id)
        if not tool:
            raise ToolNotFoundError
        return self._to_response(tool)

    async def list_tools(
        self,
        tenant_id: str,
        limit: int = 20,
        cursor: str | None = None,
        agent_name: str | None = None,
    ) -> PaginatedResponse[ToolResponse]:
        cursor_data: CursorData | None = None
        if cursor:
            cursor_data = decode_cursor(cursor)

        tools, has_more = await self._repository.list_paginated(
            tenant_id=tenant_id,
            limit=limit,
            cursor=cursor_data,
            agent_name=agent_name,
        )

        next_cursor: str | None = None
        if has_more and tools:
            last = tools[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return PaginatedResponse[ToolResponse](
            items=[self._to_response(t) for t in tools],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def update_tool(self, tenant_id: str, tool_id: str, data: ToolUpdate) -> ToolResponse:
        tool = await self._repository.get_by_id(tenant_id, tool_id)
        if not tool:
            raise ToolNotFoundError

        if "name" in data.model_fields_set and data.name is not None:
            tool.name = data.name

        if "description" in data.model_fields_set:
            tool.description = data.description

        try:
            tool = await self._repository.update(tool)
        except IntegrityError:
            raise ToolAlreadyExistsError from None
        return self._to_response(tool)

    async def delete_tool(self, tenant_id: str, tool_id: str) -> None:
        tool = await self._repository.get_by_id(tenant_id, tool_id)
        if not tool:
            raise ToolNotFoundError
        await self._repository.delete(tool)

    @staticmethod
    def _to_response(tool: Tool) -> ToolResponse:
        return ToolResponse(
            id=tool.id,
            name=tool.name,
            description=tool.description,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )
