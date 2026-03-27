from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from agent_platform.api.dependencies import get_execution_service
from agent_platform.auth.api_key import TenantId
from agent_platform.data_models.execution import ExecutionResponse
from agent_platform.data_models.pagination import PaginatedResponse
from agent_platform.exceptions import AgentNotFoundError, ExecutionNotFoundError, InvalidCursorError
from agent_platform.services.execution_service import ExecutionService
from agent_platform.settings import get_settings

agent_executions_router = APIRouter(prefix="/agents", tags=["Execution History"])
executions_router = APIRouter(prefix="/executions", tags=["Execution History"])


@agent_executions_router.get(
    "/{agent_id}/executions",
    response_model=PaginatedResponse[ExecutionResponse],
)
async def list_executions(
    tenant_id: TenantId,
    agent_id: str,
    service: Annotated[ExecutionService, Depends(get_execution_service)],
    cursor: str | None = Query(None, description="Pagination cursor"),
    limit: int = Query(
        default=get_settings().pagination_default_limit,
        ge=1,
        le=get_settings().pagination_max_limit,
        description="Items per page",
    ),
) -> PaginatedResponse[ExecutionResponse]:
    try:
        return await service.list_executions(
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=limit,
            cursor=cursor,
        )
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        ) from None
    except InvalidCursorError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination cursor.",
        ) from None


@executions_router.get(
    "/{execution_id}",
    response_model=ExecutionResponse,
)
async def get_execution(
    tenant_id: TenantId,
    execution_id: str,
    service: Annotated[ExecutionService, Depends(get_execution_service)],
) -> ExecutionResponse:
    try:
        return await service.get_execution(tenant_id, execution_id)
    except ExecutionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found.",
        ) from None
