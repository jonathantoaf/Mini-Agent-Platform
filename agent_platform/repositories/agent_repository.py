from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.data_models.pagination import CursorData
from agent_platform.db.models.agent import Agent, agent_tools
from agent_platform.db.models.tool import Tool
from agent_platform.settings import get_settings


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, agent: Agent) -> Agent:
        self._session.add(agent)
        await self._session.flush()
        await self._session.refresh(agent)
        return agent

    async def get_by_id(self, tenant_id: str, agent_id: str) -> Agent | None:
        result = await self._session.execute(
            select(Agent).where(
                Agent.tenant_id == tenant_id,
                Agent.id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: CursorData | None = None,
        tool_name: str | None = None,
    ) -> tuple[list[Agent], bool]:
        """Cursor-based pagination using (created_at, id) for stable ordering."""
        conditions = [Agent.tenant_id == tenant_id]

        if cursor:
            conditions.append(
                or_(
                    Agent.created_at < cursor.created_at,
                    and_(
                        Agent.created_at == cursor.created_at,
                        Agent.id < cursor.id,
                    ),
                )
            )

        stmt = select(Agent).where(and_(*conditions))

        if tool_name:
            stmt = stmt.join(agent_tools).join(Tool).where(Tool.name == tool_name)

        stmt = stmt.order_by(Agent.created_at.desc(), Agent.id.desc()).limit(limit + 1)

        result = await self._session.execute(stmt)
        items = list(result.unique().scalars().all())

        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        return items, has_more

    async def update(self, agent: Agent) -> Agent:
        await self._session.flush()
        await self._session.refresh(agent)
        return agent

    async def delete(self, agent: Agent) -> None:
        await self._session.delete(agent)
        await self._session.flush()
