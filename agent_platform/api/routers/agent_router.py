from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent_platform.api.dependencies import get_agent_service
from agent_platform.auth.api_key import TenantId
from agent_platform.data_models.agent import AgentCreate, AgentResponse, AgentUpdate
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    InvalidCursorError,
    ToolNotFoundError,
)
from agent_platform.services.agent_service import AgentService
from agent_platform.settings import get_settings

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent",
    description="Register a new agent with optional tool assignments.",
    responses={
        404: {"description": "One or more tool IDs not found"},
        409: {"description": "Agent with this name already exists"},
    },
)
async def create_agent(
    tenant_id: TenantId,
    data: AgentCreate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    try:
        return await service.create_agent(tenant_id, data)
    except AgentAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this name already exists.",
        ) from None
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more tool IDs not found.",
        ) from None


@router.get(
    "",
    response_model=PaginatedResponse[AgentResponse],
    summary="List agents",
    description="Retrieve a paginated list of agents for the authenticated tenant.",
    responses={400: {"description": "Invalid pagination cursor"}},
)
async def list_agents(
    tenant_id: TenantId,
    service: Annotated[AgentService, Depends(get_agent_service)],
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(
        default=get_settings().pagination_default_limit,
        ge=1,
        le=get_settings().pagination_max_limit,
        description="Items per page",
    ),
    tool_name: str | None = Query(None, description="Filter by tool name"),
) -> PaginatedResponse[AgentResponse]:
    try:
        return await service.list_agents(
            tenant_id=tenant_id,
            limit=limit,
            cursor=cursor,
            tool_name=tool_name,
        )
    except InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from None


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get an agent",
    description="Retrieve a single agent by ID.",
    responses={404: {"description": "Agent not found"}},
)
async def get_agent(
    tenant_id: TenantId,
    agent_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    try:
        return await service.get_agent(tenant_id, agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        ) from None


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update an agent",
    description="Partially update an existing agent.",
    responses={
        404: {"description": "Agent or tool not found"},
        409: {"description": "Agent with this name already exists"},
    },
)
async def update_agent(
    tenant_id: TenantId,
    agent_id: str,
    data: AgentUpdate,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> AgentResponse:
    try:
        return await service.update_agent(tenant_id, agent_id, data)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        ) from None
    except AgentAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An agent with this name already exists.",
        ) from None
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more tool IDs not found.",
        ) from None


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent",
    description="Delete an agent by ID.",
    responses={404: {"description": "Agent not found"}},
)
async def delete_agent(
    tenant_id: TenantId,
    agent_id: str,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> None:
    try:
        await service.delete_agent(tenant_id, agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        ) from None
