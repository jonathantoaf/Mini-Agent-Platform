from collections.abc import AsyncIterator
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.containers import Container
from agent_platform.db.session import Database
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.agent_service import AgentService
from agent_platform.services.tool_service import ToolService


@inject
async def get_session(
    db: Database = Depends(Provide[Container.db]),
) -> AsyncIterator[AsyncSession]:
    async for session in db.session():
        yield session


def get_tool_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ToolService:
    return ToolService(ToolRepository(session))


def get_agent_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentService:
    return AgentService(
        AgentRepository(session),
        ToolRepository(session),
    )
