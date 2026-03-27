from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.db.models.execution import Execution


class ExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, execution: Execution) -> Execution:
        self._session.add(execution)
        await self._session.flush()
        await self._session.refresh(execution)
        return execution
