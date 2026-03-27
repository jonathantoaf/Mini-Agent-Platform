import logging

from sqlalchemy.exc import IntegrityError

from agent_platform.data_models.pagination import (
    CursorData,
    PaginatedResponse,
    decode_cursor,
    encode_cursor,
)
from agent_platform.data_models.tool import ToolCreate, ToolResponse, ToolUpdate
from agent_platform.db.models.tool import Tool
from agent_platform.exceptions import ToolAlreadyExistsError, ToolNotFoundError
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.settings import get_settings


class ToolService:
    def __init__(self, repository: ToolRepository) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
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
            self._logger.warning(f"Tool already exists tenant_id={tenant_id} name={data.name}")
            raise ToolAlreadyExistsError from None
        self._logger.info(f"Created tool tenant_id={tenant_id} tool_id={tool.id} name={tool.name}")
        return self._to_response(tool)

    async def get_tool(self, tenant_id: str, tool_id: str) -> ToolResponse:
        self._logger.debug(f"Fetching tool tenant_id={tenant_id} tool_id={tool_id}")
        tool = await self._repository.get_by_id(tenant_id, tool_id)
        if not tool:
            self._logger.warning(f"Tool not found tenant_id={tenant_id} tool_id={tool_id}")
            raise ToolNotFoundError
        return self._to_response(tool)

    async def list_tools(
        self,
        tenant_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: str | None = None,
        agent_name: str | None = None,
    ) -> PaginatedResponse[ToolResponse]:
        self._logger.debug(
            f"Listing tools tenant_id={tenant_id} limit={limit} "
            f"cursor={cursor} agent_name={agent_name}"
        )
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
            self._logger.warning(f"Tool not found tenant_id={tenant_id} tool_id={tool_id}")
            raise ToolNotFoundError

        for field in data.model_fields_set:
            value = getattr(data, field)
            if value is not None or field == "description":
                setattr(tool, field, value)

        try:
            tool = await self._repository.update(tool)
        except IntegrityError:
            self._logger.warning(
                f"Tool already exists tenant_id={tenant_id} "
                f"tool_id={tool_id} name={data.name or tool.name}"
            )
            raise ToolAlreadyExistsError from None
        self._logger.info(f"Updated tool tenant_id={tenant_id} tool_id={tool.id} name={tool.name}")
        return self._to_response(tool)

    async def delete_tool(self, tenant_id: str, tool_id: str) -> None:
        tool = await self._repository.get_by_id(tenant_id, tool_id)
        if not tool:
            self._logger.warning(f"Tool not found tenant_id={tenant_id} tool_id={tool_id}")
            raise ToolNotFoundError
        await self._repository.delete(tool)
        self._logger.info(f"Deleted tool tenant_id={tenant_id} tool_id={tool_id}")

    @staticmethod
    def _to_response(tool: Tool) -> ToolResponse:
        return ToolResponse(
            id=tool.id,
            name=tool.name,
            description=tool.description,
            created_at=tool.created_at,
            updated_at=tool.updated_at,
        )
