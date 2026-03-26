from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.data_models.pagination import CursorData
from agent_platform.db.models.tool import Tool


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

    async def list_paginated(
        self,
        tenant_id: str,
        limit: int = 20,
        cursor: CursorData | None = None,
        agent_name: str | None = None,
    ) -> tuple[list[Tool], bool]:
        """Cursor-based pagination using (created_at, id) for stable ordering.

        agent_name filter is stubbed until the agent_tools join table exists (Task 2).
        """
        _ = agent_name  # stubbed until Task 2

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

        stmt = (
            select(Tool)
            .where(and_(*conditions))
            .order_by(Tool.created_at.desc(), Tool.id.desc())
            .limit(limit + 1)
        )

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
