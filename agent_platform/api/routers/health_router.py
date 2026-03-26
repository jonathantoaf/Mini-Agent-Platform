from fastapi import APIRouter

from agent_platform.data_models.health import HealthResponse

router = APIRouter(
    prefix="",
    tags=["Health"],
)


@router.get(
    path="/health",
    response_model=HealthResponse,
)
def health() -> HealthResponse:
    return HealthResponse()
