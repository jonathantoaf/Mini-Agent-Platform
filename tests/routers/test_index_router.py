"""Unit tests for the Index router."""

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.api.routers.index_router import router
from agent_platform.data_models.info import InfoResponse
from agent_platform.settings import get_settings


def test_index() -> None:
    settings = get_settings()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == status.HTTP_200_OK
    expected = InfoResponse(api=settings.app_name, version=settings.app_version)
    assert InfoResponse(**response.json()) == expected
