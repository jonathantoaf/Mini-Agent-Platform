import logging

from sqlalchemy.exc import IntegrityError

from agent_platform.data_models.agent import AgentCreate, AgentResponse, AgentUpdate
from agent_platform.data_models.pagination import (
    CursorData,
    PaginatedResponse,
    decode_cursor,
    encode_cursor,
)
from agent_platform.data_models.tool import ToolResponse
from agent_platform.db.models.agent import Agent
from agent_platform.db.models.tool import Tool
from agent_platform.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ToolNotFoundError,
)
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.settings import get_settings


class AgentService:
    def __init__(self, repository: AgentRepository, tool_repository: ToolRepository) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._repository = repository
        self._tool_repository = tool_repository

    async def _resolve_tools(self, tenant_id: str, tool_ids: list[str]) -> list[Tool]:
        """Validate tool_ids belong to the tenant and return the Tool objects."""
        if not tool_ids:
            return []
        tools = await self._tool_repository.get_by_ids(tenant_id, tool_ids)
        if len(tools) != len(tool_ids):
            self._logger.warning(
                f"Invalid tool_ids for agent tenant_id={tenant_id} "
                f"requested={len(tool_ids)} resolved={len(tools)}"
            )
            raise ToolNotFoundError
        return tools

    async def create_agent(self, tenant_id: str, data: AgentCreate) -> AgentResponse:
        tools = await self._resolve_tools(tenant_id, data.tool_ids)
        agent = Agent(
            tenant_id=tenant_id,
            name=data.name,
            role=data.role,
            description=data.description,
        )
        agent.tools = tools
        try:
            agent = await self._repository.create(agent)
        except IntegrityError:
            self._logger.warning(f"Agent already exists tenant_id={tenant_id} name={data.name}")
            raise AgentAlreadyExistsError from None
        self._logger.info(
            f"Created agent tenant_id={tenant_id} agent_id={agent.id} "
            f"name={agent.name} tool_count={len(agent.tools)}"
        )
        return self._to_response(agent)

    async def get_agent(self, tenant_id: str, agent_id: str) -> AgentResponse:
        self._logger.debug(f"Fetching agent tenant_id={tenant_id} agent_id={agent_id}")
        agent = await self._repository.get_by_id(tenant_id, agent_id)
        if not agent:
            self._logger.warning(f"Agent not found tenant_id={tenant_id} agent_id={agent_id}")
            raise AgentNotFoundError
        return self._to_response(agent)

    async def list_agents(
        self,
        tenant_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: str | None = None,
        tool_name: str | None = None,
    ) -> PaginatedResponse[AgentResponse]:
        self._logger.debug(
            f"Listing agents tenant_id={tenant_id} limit={limit} "
            f"cursor={cursor} tool_name={tool_name}"
        )
        cursor_data: CursorData | None = None
        if cursor:
            cursor_data = decode_cursor(cursor)

        agents, has_more = await self._repository.list_paginated(
            tenant_id=tenant_id,
            limit=limit,
            cursor=cursor_data,
            tool_name=tool_name,
        )

        next_cursor: str | None = None
        if has_more and agents:
            last = agents[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return PaginatedResponse[AgentResponse](
            items=[self._to_response(a) for a in agents],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def update_agent(self, tenant_id: str, agent_id: str, data: AgentUpdate) -> AgentResponse:
        agent = await self._repository.get_by_id(tenant_id, agent_id)
        if not agent:
            self._logger.warning(f"Agent not found tenant_id={tenant_id} agent_id={agent_id}")
            raise AgentNotFoundError

        for field in data.model_fields_set - {"tool_ids"}:
            value = getattr(data, field)
            if value is not None or field == "description":
                setattr(agent, field, value)

        if "tool_ids" in data.model_fields_set:
            agent.tools = await self._resolve_tools(tenant_id, data.tool_ids or [])

        try:
            agent = await self._repository.update(agent)
        except IntegrityError:
            self._logger.warning(
                f"Agent already exists tenant_id={tenant_id} "
                f"agent_id={agent_id} name={data.name or agent.name}"
            )
            raise AgentAlreadyExistsError from None
        self._logger.info(
            f"Updated agent tenant_id={tenant_id} agent_id={agent.id} "
            f"name={agent.name} tool_count={len(agent.tools)}"
        )
        return self._to_response(agent)

    async def delete_agent(self, tenant_id: str, agent_id: str) -> None:
        agent = await self._repository.get_by_id(tenant_id, agent_id)
        if not agent:
            self._logger.warning(f"Agent not found tenant_id={tenant_id} agent_id={agent_id}")
            raise AgentNotFoundError
        await self._repository.delete(agent)
        self._logger.info(f"Deleted agent tenant_id={tenant_id} agent_id={agent_id}")

    @staticmethod
    def _to_response(agent: Agent) -> AgentResponse:
        return AgentResponse(
            id=agent.id,
            name=agent.name,
            role=agent.role,
            description=agent.description,
            tools=[
                ToolResponse(
                    id=t.id,
                    name=t.name,
                    description=t.description,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
                for t in agent.tools
            ],
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
