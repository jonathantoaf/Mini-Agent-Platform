from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.data_models.health import HealthResponse


def test_health(api_client: TestClient) -> None:
    # Act
    response = api_client.get("/health")

    # Assert
    assert response.status_code == status.HTTP_200_OK

    actual = HealthResponse(**response.json())
    expected = HealthResponse()
    assert actual == expected
