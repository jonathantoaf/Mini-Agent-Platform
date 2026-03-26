import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient

from agent_platform.api.server import app


@pytest.fixture(scope="session")
def api_client() -> TestClient:
    async def test_error(_: Request) -> Response:
        raise Exception("Test Error")  # noqa: TRY002, TRY003

    app.add_api_route("/test_error", test_error)

    return TestClient(app, raise_server_exceptions=False)
