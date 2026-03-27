from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent_platform.api.dependencies import get_agent_service
from agent_platform.auth.api_key import TenantId
from agent_platform.data_models.agent import AgentCreate, AgentResponse, AgentUpdate
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    ToolNotFoundError,
)
from agent_platform.services.agent_service import AgentService
from agent_platform.settings import get_settings

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("", response_model=PaginatedResponse[AgentResponse])
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
    return await service.list_agents(
        tenant_id=tenant_id,
        limit=limit,
        cursor=cursor,
        tool_name=tool_name,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
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


@router.patch("/{agent_id}", response_model=AgentResponse)
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


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
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
