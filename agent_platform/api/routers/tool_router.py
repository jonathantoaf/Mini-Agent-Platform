from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent_platform.api.dependencies import get_tool_service
from agent_platform.auth.api_key import TenantId
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.data_models.tool import ToolCreate, ToolResponse, ToolUpdate
from agent_platform.exceptions import InvalidCursorError, ToolAlreadyExistsError, ToolNotFoundError
from agent_platform.services.tool_service import ToolService
from agent_platform.settings import get_settings

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tenant_id: TenantId,
    data: ToolCreate,
    service: Annotated[ToolService, Depends(get_tool_service)],
) -> ToolResponse:
    try:
        return await service.create_tool(tenant_id, data)
    except ToolAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tool with this name already exists.",
        ) from None


@router.get("", response_model=PaginatedResponse[ToolResponse])
async def list_tools(
    tenant_id: TenantId,
    service: Annotated[ToolService, Depends(get_tool_service)],
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(
        default=get_settings().pagination_default_limit,
        ge=1,
        le=get_settings().pagination_max_limit,
        description="Items per page",
    ),
    agent_name: str | None = Query(None, description="Filter by agent name"),
) -> PaginatedResponse[ToolResponse]:
    try:
        return await service.list_tools(
            tenant_id=tenant_id,
            limit=limit,
            cursor=cursor,
            agent_name=agent_name,
        )
    except InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from None


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tenant_id: TenantId,
    tool_id: str,
    service: Annotated[ToolService, Depends(get_tool_service)],
) -> ToolResponse:
    try:
        return await service.get_tool(tenant_id, tool_id)
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        ) from None


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tenant_id: TenantId,
    tool_id: str,
    data: ToolUpdate,
    service: Annotated[ToolService, Depends(get_tool_service)],
) -> ToolResponse:
    try:
        return await service.update_tool(tenant_id, tool_id, data)
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        ) from None
    except ToolAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tool with this name already exists.",
        ) from None


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tenant_id: TenantId,
    tool_id: str,
    service: Annotated[ToolService, Depends(get_tool_service)],
) -> None:
    try:
        await service.delete_tool(tenant_id, tool_id)
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found.",
        ) from None
