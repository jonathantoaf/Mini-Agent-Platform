from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.data_models.pagination import CursorData
from agent_platform.db.models.execution import Execution
from agent_platform.settings import get_settings


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, execution: Execution) -> Execution:
        self._session.add(execution)
        await self._session.flush()
        await self._session.refresh(execution)
        return execution

    async def get_by_id(self, tenant_id: str, execution_id: str) -> Execution | None:
        result = await self._session.execute(
            select(Execution).where(
                Execution.tenant_id == tenant_id,
                Execution.id == execution_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        tenant_id: str,
        agent_id: str,
        limit: int = get_settings().pagination_default_limit,
        cursor: CursorData | None = None,
    ) -> tuple[list[Execution], bool]:
        """Cursor-based pagination using (created_at, id) for stable ordering."""
        conditions = [Execution.tenant_id == tenant_id, Execution.agent_id == agent_id]

        if cursor:
            conditions.append(
                or_(
                    Execution.created_at < cursor.created_at,
                    and_(
                        Execution.created_at == cursor.created_at,
                        Execution.id < cursor.id,
                    ),
                )
            )

        stmt = (
            select(Execution)
            .where(and_(*conditions))
            .order_by(Execution.created_at.desc(), Execution.id.desc())
            .limit(limit + 1)
        )

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        return items, has_more
