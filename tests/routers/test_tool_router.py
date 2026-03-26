"""Integration tests for Tool CRUD endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

TENANT_1_HEADERS = {"X-API-Key": "sk-tenant1-secret"}
TENANT_2_HEADERS = {"X-API-Key": "sk-tenant2-secret"}
BASE_URL = "/api/v1/tools"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tool(
    client: TestClient,
    name: str,
    description: str | None = None,
    headers: dict | None = None,
) -> dict:
    payload: dict = {"name": name}
    if description is not None:
        payload["description"] = description
    resp = client.post(BASE_URL, json=payload, headers=headers or TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _delete_all(client: TestClient, headers: dict) -> None:
    resp = client.get(BASE_URL, params={"limit": 100}, headers=headers)
    if resp.status_code == status.HTTP_200_OK:
        for tool in resp.json()["items"]:
            client.delete(f"{BASE_URL}/{tool['id']}", headers=headers)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup(api_client: TestClient):
    """Delete all tools for both tenants after each test."""
    yield
    _delete_all(api_client, TENANT_1_HEADERS)
    _delete_all(api_client, TENANT_2_HEADERS)


@pytest.fixture()
def tool(api_client: TestClient) -> dict:
    """Pre-created tool for tenant_1."""
    return _create_tool(api_client, "web-search", "Search the web")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        ({}, status.HTTP_401_UNAUTHORIZED),
        ({"X-API-Key": "invalid-key"}, status.HTTP_401_UNAUTHORIZED),
    ],
    ids=["missing-key", "invalid-key"],
)
def test_auth_rejection(api_client: TestClient, headers: dict, expected_status: int) -> None:
    resp = api_client.get(BASE_URL, headers=headers)
    assert resp.status_code == expected_status


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_tool(api_client: TestClient) -> None:
    resp = api_client.post(
        BASE_URL,
        json={"name": "summarizer", "description": "Summarize text"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["name"] == "summarizer"
    assert body["description"] == "Summarize text"
    assert "id" in body
    assert "createdAt" in body
    assert "updatedAt" in body
    # tenant_id must not be exposed
    assert "tenantId" not in body
    assert "tenant_id" not in body


def test_create_tool_without_description(api_client: TestClient) -> None:
    resp = api_client.post(BASE_URL, json={"name": "no-desc-tool"}, headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["description"] is None


def test_create_tool_duplicate_name(api_client: TestClient) -> None:
    _create_tool(api_client, "dup-tool")
    resp = api_client.post(BASE_URL, json={"name": "dup-tool"}, headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "x" * 256},
    ],
    ids=["missing-name", "empty-name", "name-too-long"],
)
def test_create_tool_validation_error(api_client: TestClient, payload: dict) -> None:
    resp = api_client.post(BASE_URL, json=payload, headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def test_get_tool(api_client: TestClient, tool: dict) -> None:
    resp = api_client.get(f"{BASE_URL}/{tool['id']}", headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == tool["id"]
    assert resp.json()["name"] == tool["name"]


def test_get_tool_not_found(api_client: TestClient) -> None:
    resp = api_client.get(f"{BASE_URL}/nonexistent-id", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# List + Pagination
# ---------------------------------------------------------------------------


def test_list_tools_empty(api_client: TestClient) -> None:
    resp = api_client.get(BASE_URL, headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["items"] == []
    assert body["hasMore"] is False
    assert body["nextCursor"] is None


def test_list_tools_pagination(api_client: TestClient) -> None:
    page_size = 2
    for i in range(3):
        _create_tool(api_client, f"tool-{i}")

    # Page 1
    resp = api_client.get(BASE_URL, params={"limit": page_size}, headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_200_OK
    page1 = resp.json()
    assert len(page1["items"]) == page_size
    assert page1["hasMore"] is True
    assert page1["nextCursor"] is not None

    # Page 2: use cursor
    resp = api_client.get(
        BASE_URL,
        params={"limit": page_size, "cursor": page1["nextCursor"]},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_200_OK
    page2 = resp.json()
    assert len(page2["items"]) == 1
    assert page2["hasMore"] is False

    # No overlap between pages
    page1_ids = {t["id"] for t in page1["items"]}
    page2_ids = {t["id"] for t in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_tool_name(api_client: TestClient, tool: dict) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={"name": "renamed-tool"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == "renamed-tool"
    assert resp.json()["description"] == tool["description"]


def test_update_tool_description_only(api_client: TestClient, tool: dict) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={"description": "Updated description"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == tool["name"]
    assert resp.json()["description"] == "Updated description"


def test_update_tool_duplicate_name(api_client: TestClient) -> None:
    _create_tool(api_client, "tool-a")
    tool_b = _create_tool(api_client, "tool-b")

    resp = api_client.patch(
        f"{BASE_URL}/{tool_b['id']}",
        json={"name": "tool-a"},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


def test_update_tool_empty_body(api_client: TestClient, tool: dict) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == tool["name"]
    assert resp.json()["description"] == tool["description"]


def test_update_tool_same_name(api_client: TestClient, tool: dict) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={"name": tool["name"]},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK


def test_update_tool_clear_description(api_client: TestClient) -> None:
    tool = _create_tool(api_client, "has-desc", "Some description")
    assert tool["description"] == "Some description"

    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={"description": None},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["description"] is None


def test_update_tool_not_found(api_client: TestClient) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/nonexistent-id",
        json={"name": "x"},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_tool(api_client: TestClient, tool: dict) -> None:
    resp = api_client.delete(f"{BASE_URL}/{tool['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify gone
    resp = api_client.get(f"{BASE_URL}/{tool['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_tool_not_found(api_client: TestClient) -> None:
    resp = api_client.delete(f"{BASE_URL}/nonexistent-id", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation_get(api_client: TestClient, tool: dict) -> None:
    """Tool created by tenant_1 is invisible to tenant_2 (returns 404, not 403)."""
    resp = api_client.get(f"{BASE_URL}/{tool['id']}", headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_tenant_isolation_list(api_client: TestClient, tool: dict) -> None:
    """Tenant_2 list does not include tenant_1's tools."""
    # tool fixture ensures tenant_1 has data
    assert tool["id"]  # sanity check
    resp = api_client.get(BASE_URL, headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["items"] == []


def test_tenant_isolation_update(api_client: TestClient, tool: dict) -> None:
    resp = api_client.patch(
        f"{BASE_URL}/{tool['id']}",
        json={"name": "hacked"},
        headers=TENANT_2_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_tenant_isolation_delete(api_client: TestClient, tool: dict) -> None:
    resp = api_client.delete(f"{BASE_URL}/{tool['id']}", headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Verify still exists for the owning tenant
    resp = api_client.get(f"{BASE_URL}/{tool['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_200_OK


def test_tenant_isolation_duplicate_name_allowed(api_client: TestClient) -> None:
    """Different tenants can use the same tool name."""
    resp1 = api_client.post(BASE_URL, json={"name": "shared-name"}, headers=TENANT_1_HEADERS)
    resp2 = api_client.post(BASE_URL, json={"name": "shared-name"}, headers=TENANT_2_HEADERS)
    assert resp1.status_code == status.HTTP_201_CREATED
    assert resp2.status_code == status.HTTP_201_CREATED
