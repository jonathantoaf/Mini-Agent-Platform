import logging
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request, Response, status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from agent_platform.api import server

TENANT_1_HEADERS = {"X-API-Key": "sk-tenant1-secret"}


@pytest.fixture()
def api_client() -> TestClient:
    test_app = server.create_app()

    async def test_error(_: Request) -> Response:
        raise Exception("Test Error")  # noqa: TRY002, TRY003

    if not any(route.path == "/test_error" for route in test_app.routes):
        test_app.add_api_route("/test_error", test_error)

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


def test_request_logging_includes_request_id(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api_client.get("/health")

    assert response.status_code == status.HTTP_200_OK

    start_record = next(
        record
        for record in caplog.records
        if record.getMessage() == "Request started method=GET path=/health"
    )
    end_record = next(
        record
        for record in caplog.records
        if record.getMessage().startswith(
            "Request completed method=GET path=/health status_code=200"
        )
    )

    assert start_record.request_id != "-"
    assert start_record.request_id == end_record.request_id


def test_authenticated_request_logging_includes_tenant_id(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api_client.get("/api/v1/tools", headers=TENANT_1_HEADERS)

    assert response.status_code == status.HTTP_200_OK

    end_record = next(
        record
        for record in caplog.records
        if record.getMessage().startswith(
            "Request completed method=GET path=/api/v1/tools status_code=200"
        )
    )

    assert end_record.tenant_id == "tenant_1"


def test_unexpected_exception_logged_once(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)

    response = api_client.get("/test_error")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert (
        sum(
            "Unhandled exception method=GET path=/test_error" in record.getMessage()
            for record in caplog.records
        )
        == 1
    )


def test_domain_error_not_double_logged(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)

    response = api_client.get("/api/v1/tools/missing", headers=TENANT_1_HEADERS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert (
        sum(
            "Tool not found tenant_id=tenant_1 tool_id=missing" in record.getMessage()
            for record in caplog.records
        )
        == 1
    )
    assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_create_app_disposes_db_on_shutdown(mocker: MockerFixture) -> None:
    mock_db = Mock()
    mock_db.dispose = AsyncMock()
    mock_container = Mock()
    mock_container.init_resources = AsyncMock()
    mock_container.shutdown_resources = AsyncMock()
    mock_container.db = Mock(return_value=mock_db)

    mocker.patch.object(server, "create_container", return_value=mock_container)

    test_app = server.create_app()

    with TestClient(test_app):
        pass

    mock_container.init_resources.assert_awaited_once()
    mock_db.dispose.assert_awaited_once()
    mock_container.shutdown_resources.assert_awaited_once()
