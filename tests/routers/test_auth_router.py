from fastapi import status
from fastapi.testclient import TestClient


def test_missing_api_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/tools")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Missing API key. Provide X-API-Key header."


def test_invalid_api_key(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/tools", headers={"X-API-Key": "sk-invalid"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.json()["detail"] == "Invalid API key."
