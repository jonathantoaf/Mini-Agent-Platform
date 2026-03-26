from agent_platform.data_models.base import SharedBaseModel


class HealthResponse(SharedBaseModel):
    status: str = "OK"
