from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel


class HealthResponse(SharedBaseModel):
    status: str = Field(default="OK", description="Service health status")
