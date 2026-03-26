import pytest
from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.settings import get_settings


def test_docs(api_client: TestClient) -> None:
    settings = get_settings()

    # Act
    response = api_client.get("/docs")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"

    html_content = response.content.decode()
    assert f"<title>{settings.app_name} - Swagger UI</title>" in html_content


def test_redoc(api_client: TestClient) -> None:
    settings = get_settings()

    # Act
    response = api_client.get("/redoc")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"

    html_content = response.content.decode()
    assert f"<title>{settings.app_name} - ReDoc</title>" in html_content


def test_openapi(api_client: TestClient) -> None:
    settings = get_settings()

    # Act
    response = api_client.get("/openapi.json")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Content-Type"] == "application/json"

    json_content = response.json()
    assert json_content["info"] == {
        "title": settings.app_name,
        "version": settings.app_version,
    }


@pytest.mark.parametrize(
    "file_name, expected_content_length",
    [
        pytest.param(
            "favicon.png",
            "5043",
            marks=pytest.mark.parametrize,
            id="favicon.png",
        ),
        pytest.param(
            "redoc.standalone.js",
            "1042008",
            marks=pytest.mark.parametrize,
            id="redoc.standalone.js",
        ),
        pytest.param(
            "swagger-ui-bundle.js",
            "1385226",
            marks=pytest.mark.parametrize,
            id="swagger-ui-bundle.js",
        ),
        pytest.param(
            "swagger-ui.css",
            "151211",
            marks=pytest.mark.parametrize,
            id="swagger-ui.css",
        ),
    ],
)
def test_static(api_client: TestClient, file_name: str, expected_content_length: str) -> None:
    # Act
    response = api_client.get(f"/static/{file_name}")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Content-Length"] == expected_content_length


def test_exception_handler(api_client: TestClient) -> None:
    # Act
    response = api_client.get("/test_error")

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
