from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from agent_platform.api.dependencies import get_run_service
from agent_platform.auth.api_key import TenantId
from agent_platform.data_models.run import RunRequest, RunResponse
from agent_platform.exceptions import (
    AgentNotFoundError,
    InvalidModelError,
    MaxIterationsError,
    PromptInjectionError,
    ToolNotAssignedError,
)
from agent_platform.services.run.run_service import RunService

router = APIRouter(prefix="/agents", tags=["Run Agent"])


@router.post(
    "/{agent_id}/run",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run an agent",
    description="Execute an agent with a task using the specified model.",
    responses={
        400: {"description": "Invalid model, prompt injection detected, or tool not assigned"},
        404: {"description": "Agent not found"},
        500: {"description": "Execution exceeded maximum iterations"},
    },
)
async def run_agent(
    tenant_id: TenantId,
    agent_id: str,
    data: RunRequest,
    service: Annotated[RunService, Depends(get_run_service)],
) -> RunResponse:
    try:
        return await service.run_agent(tenant_id, agent_id, data)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        ) from None
    except PromptInjectionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt injection detected.",
        ) from None
    except InvalidModelError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid model. Check allowed models.",
        ) from None
    except ToolNotAssignedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool not assigned to this agent.",
        ) from None
    except MaxIterationsError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Execution exceeded maximum iterations.",
        ) from None
