from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.data_models.pagination import CursorData
from agent_platform.db.models.agent import Agent, agent_tools
from agent_platform.db.models.tool import Tool
from agent_platform.settings import get_settings


class ToolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tool: Tool) -> Tool:
        self._session.add(tool)
        await self._session.flush()
        await self._session.refresh(tool)
        return tool

    async def get_by_id(self, tenant_id: str, tool_id: str) -> Tool | None:
        result = await self._session.execute(
            select(Tool).where(
                Tool.tenant_id == tenant_id,
                Tool.id == tool_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, tenant_id: str, tool_ids: list[str]) -> list[Tool]:
        result = await self._session.execute(
            select(Tool).where(
                Tool.tenant_id == tenant_id,
                Tool.id.in_(tool_ids),
            )
        )
        return list(result.scalars().all())

    async def list_paginated(
        self,
        tenant_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: CursorData | None = None,
        agent_name: str | None = None,
    ) -> tuple[list[Tool], bool]:
        """Cursor-based pagination using (created_at, id) for stable ordering."""
        conditions = [Tool.tenant_id == tenant_id]

        if cursor:
            conditions.append(
                or_(
                    Tool.created_at < cursor.created_at,
                    and_(
                        Tool.created_at == cursor.created_at,
                        Tool.id < cursor.id,
                    ),
                )
            )

        stmt = select(Tool).where(and_(*conditions))

        if agent_name:
            stmt = stmt.join(agent_tools).join(Agent).where(Agent.name == agent_name)

        stmt = stmt.order_by(Tool.created_at.desc(), Tool.id.desc()).limit(limit + 1)

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        return items, has_more

    async def update(self, tool: Tool) -> Tool:
        await self._session.flush()
        await self._session.refresh(tool)
        return tool

    async def delete(self, tool: Tool) -> None:
        await self._session.delete(tool)
        await self._session.flush()
