"""Unit tests for the Health router."""

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.api.routers.health_router import router
from agent_platform.data_models.health import HealthResponse


def test_health() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert HealthResponse(**response.json()) == HealthResponse()
