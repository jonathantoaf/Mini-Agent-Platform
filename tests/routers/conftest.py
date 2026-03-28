"""Shared fixtures for router tests."""

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.testclient import TestClient

from agent_platform.api.server import app
from agent_platform.auth.api_key import get_current_tenant_id

TENANT_ID = "tenant_1"


def make_test_client(
    router: APIRouter,
    service_override: tuple[Callable, AsyncMock],
    prefix: str = "/api/v1",
) -> TestClient:
    """Create a minimal test client with a single router and mocked service."""
    test_app = FastAPI()
    test_app.include_router(router, prefix=prefix)
    dep_fn, mock = service_override
    test_app.dependency_overrides[dep_fn] = lambda: mock
    test_app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID
    return TestClient(test_app)


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Integration test fixture (used by test_rls, test_docs, test_server_logging)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_client() -> TestClient:
    async def test_error(_: Request) -> Response:
        raise Exception("Test Error")  # noqa: TRY002, TRY003

    app.add_api_route("/test_error", test_error)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
