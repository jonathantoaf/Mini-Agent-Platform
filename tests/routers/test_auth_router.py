"""Unit tests for API key authentication."""

from unittest.mock import AsyncMock

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import get_tool_service
from agent_platform.api.routers.tool_router import router


def _make_client() -> TestClient:
    """Create a test client with real auth but mocked service (no DB needed)."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    mock = AsyncMock()
    app.dependency_overrides[get_tool_service] = lambda: mock
    return TestClient(app)


def test_missing_api_key() -> None:
    client = _make_client()
    resp = client.get("/api/v1/tools")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Missing API key. Provide X-API-Key header."


def test_invalid_api_key() -> None:
    client = _make_client()
    resp = client.get("/api/v1/tools", headers={"X-API-Key": "sk-invalid"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Invalid API key."
