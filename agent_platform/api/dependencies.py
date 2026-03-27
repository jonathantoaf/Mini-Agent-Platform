import json
from collections.abc import AsyncIterator
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.containers import Container
from agent_platform.db.session import Database
from agent_platform.repositories.agent_repository import AgentRepository
from agent_platform.repositories.execution_repository import ExecutionRepository
from agent_platform.repositories.tool_repository import ToolRepository
from agent_platform.services.agent_service import AgentService
from agent_platform.services.execution_service import ExecutionService
from agent_platform.services.run.guardrail import PromptInjectionGuardrail
from agent_platform.services.run.mock_llm import MockLlmAdapter
from agent_platform.services.run.mock_tool_executor import MockToolExecutor
from agent_platform.services.run.prompt_builder import PromptBuilder
from agent_platform.services.run.run_service import RunService
from agent_platform.services.tool_service import ToolService
from agent_platform.settings import get_settings


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


def get_execution_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExecutionService:
    return ExecutionService(
        execution_repo=ExecutionRepository(session),
        agent_repo=AgentRepository(session),
    )


@inject
def get_run_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    guardrail: PromptInjectionGuardrail = Depends(Provide[Container.guardrail]),
    mock_llm: MockLlmAdapter = Depends(Provide[Container.mock_llm]),
    tool_executor: MockToolExecutor = Depends(Provide[Container.mock_tool_executor]),
    prompt_builder: PromptBuilder = Depends(Provide[Container.prompt_builder]),
) -> RunService:
    settings = get_settings()
    return RunService(
        agent_repo=AgentRepository(session),
        execution_repo=ExecutionRepository(session),
        guardrail=guardrail,
        llm=mock_llm,
        tool_executor=tool_executor,
        prompt_builder=prompt_builder,
        allowed_models=json.loads(settings.allowed_models),
        max_iterations=settings.run_max_iterations,
    )
