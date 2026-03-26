from fastapi import APIRouter

from agent_platform.data_models.info import InfoResponse
from agent_platform.settings import get_settings

router = APIRouter(
    prefix="",
    tags=["Index"],
)


@router.get(
    path="/",
    response_model=InfoResponse,
)
def index() -> InfoResponse:
    settings = get_settings()
    return InfoResponse(api=settings.app_name, version=settings.app_version)
