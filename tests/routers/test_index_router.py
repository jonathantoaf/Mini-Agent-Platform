from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.data_models.info import InfoResponse
from agent_platform.settings import get_settings


def test_index(api_client: TestClient) -> None:
    settings = get_settings()

    # Act
    response = api_client.get("/")

    # Assert
    assert response.status_code == status.HTTP_200_OK

    actual = InfoResponse(**response.json())
    expected = InfoResponse(api=settings.app_name, version=settings.app_version)
    assert actual == expected
