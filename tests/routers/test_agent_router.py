"""Integration tests for Agent CRUD endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

TENANT_1_HEADERS = {"X-API-Key": "sk-tenant1-secret"}
TENANT_2_HEADERS = {"X-API-Key": "sk-tenant2-secret"}
AGENTS_URL = "/api/v1/agents"
TOOLS_URL = "/api/v1/tools"


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
    resp = client.post(TOOLS_URL, json=payload, headers=headers or TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _create_agent(
    client: TestClient,
    name: str,
    role: str = "assistant",
    description: str | None = None,
    tool_ids: list[str] | None = None,
    headers: dict | None = None,
) -> dict:
    payload: dict = {"name": name, "role": role}
    if description is not None:
        payload["description"] = description
    if tool_ids is not None:
        payload["toolIds"] = tool_ids
    resp = client.post(AGENTS_URL, json=payload, headers=headers or TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _delete_all_agents(client: TestClient, headers: dict) -> None:
    resp = client.get(AGENTS_URL, params={"limit": 100}, headers=headers)
    if resp.status_code == status.HTTP_200_OK:
        for agent in resp.json()["items"]:
            client.delete(f"{AGENTS_URL}/{agent['id']}", headers=headers)


def _delete_all_tools(client: TestClient, headers: dict) -> None:
    resp = client.get(TOOLS_URL, params={"limit": 100}, headers=headers)
    if resp.status_code == status.HTTP_200_OK:
        for tool in resp.json()["items"]:
            client.delete(f"{TOOLS_URL}/{tool['id']}", headers=headers)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup(api_client: TestClient):
    """Delete all agents and tools for both tenants after each test."""
    yield
    for headers in (TENANT_1_HEADERS, TENANT_2_HEADERS):
        _delete_all_agents(api_client, headers)
        _delete_all_tools(api_client, headers)


@pytest.fixture()
def tool(api_client: TestClient) -> dict:
    """Pre-created tool for tenant_1."""
    return _create_tool(api_client, "web-search", "Search the web")


@pytest.fixture()
def agent(api_client: TestClient) -> dict:
    """Pre-created agent for tenant_1."""
    return _create_agent(api_client, "my-agent", "assistant", "An agent")


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
    resp = api_client.get(AGENTS_URL, headers=headers)
    assert resp.status_code == expected_status


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_agent(api_client: TestClient) -> None:
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "test-agent", "role": "researcher", "description": "A researcher"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["name"] == "test-agent"
    assert body["role"] == "researcher"
    assert body["description"] == "A researcher"
    assert body["tools"] == []
    assert "id" in body
    assert "createdAt" in body
    assert "updatedAt" in body
    assert "tenantId" not in body
    assert "tenant_id" not in body


def test_create_agent_with_tools(api_client: TestClient, tool: dict) -> None:
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "tooled-agent", "role": "assistant", "toolIds": [tool["id"]]},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert len(body["tools"]) == 1
    assert body["tools"][0]["id"] == tool["id"]
    assert body["tools"][0]["name"] == tool["name"]


def test_create_agent_without_description(api_client: TestClient) -> None:
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "no-desc", "role": "assistant"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["description"] is None


def test_create_agent_duplicate_name(api_client: TestClient) -> None:
    _create_agent(api_client, "dup-agent")
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "dup-agent", "role": "assistant"},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


def test_create_agent_invalid_tool_ids(api_client: TestClient) -> None:
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "bad-tools", "role": "assistant", "toolIds": ["nonexistent"]},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_create_agent_cross_tenant_tool_ids(api_client: TestClient, tool: dict) -> None:
    """Tenant_2 cannot assign tenant_1's tools."""
    resp = api_client.post(
        AGENTS_URL,
        json={"name": "cross-agent", "role": "assistant", "toolIds": [tool["id"]]},
        headers=TENANT_2_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "assistant"},
        {"name": "x"},
        {"name": "", "role": "assistant"},
        {"name": "x" * 256, "role": "assistant"},
    ],
    ids=["missing-name", "missing-role", "empty-name", "name-too-long"],
)
def test_create_agent_validation_error(api_client: TestClient, payload: dict) -> None:
    resp = api_client.post(AGENTS_URL, json=payload, headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def test_get_agent(api_client: TestClient, agent: dict) -> None:
    resp = api_client.get(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == agent["id"]
    assert resp.json()["name"] == agent["name"]


def test_get_agent_not_found(api_client: TestClient) -> None:
    resp = api_client.get(f"{AGENTS_URL}/nonexistent-id", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# List + Pagination
# ---------------------------------------------------------------------------


def test_list_agents_empty(api_client: TestClient) -> None:
    resp = api_client.get(AGENTS_URL, headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["items"] == []
    assert body["hasMore"] is False
    assert body["nextCursor"] is None


def test_list_agents_pagination(api_client: TestClient) -> None:
    page_size = 2
    for i in range(3):
        _create_agent(api_client, f"agent-{i}")

    # Page 1
    resp = api_client.get(AGENTS_URL, params={"limit": page_size}, headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_200_OK
    page1 = resp.json()
    assert len(page1["items"]) == page_size
    assert page1["hasMore"] is True
    assert page1["nextCursor"] is not None

    # Page 2: use cursor
    resp = api_client.get(
        AGENTS_URL,
        params={"limit": page_size, "cursor": page1["nextCursor"]},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_200_OK
    page2 = resp.json()
    assert len(page2["items"]) == 1
    assert page2["hasMore"] is False

    # No overlap
    page1_ids = {a["id"] for a in page1["items"]}
    page2_ids = {a["id"] for a in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_list_agents_filter_by_tool_name(api_client: TestClient, tool: dict) -> None:
    agent_with_tool = _create_agent(api_client, "with-tool", tool_ids=[tool["id"]])
    _create_agent(api_client, "without-tool")

    resp = api_client.get(AGENTS_URL, params={"tool_name": tool["name"]}, headers=TENANT_1_HEADERS)

    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == agent_with_tool["id"]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_agent_name(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"name": "renamed-agent"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == "renamed-agent"
    assert resp.json()["role"] == agent["role"]


def test_update_agent_role(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"role": "researcher"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["role"] == "researcher"


def test_update_agent_description(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"description": "Updated"},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["description"] == "Updated"


def test_update_agent_tools(api_client: TestClient, agent: dict, tool: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"toolIds": [tool["id"]]},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()["tools"]) == 1
    assert resp.json()["tools"][0]["id"] == tool["id"]


def test_update_agent_clear_tools(api_client: TestClient, tool: dict) -> None:
    agent = _create_agent(api_client, "has-tools", tool_ids=[tool["id"]])
    assert len(agent["tools"]) == 1

    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"toolIds": []},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["tools"] == []


def test_update_agent_clear_description(api_client: TestClient) -> None:
    agent = _create_agent(api_client, "has-desc", description="Some description")
    assert agent["description"] == "Some description"

    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"description": None},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["description"] is None


def test_update_agent_empty_body(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={},
        headers=TENANT_1_HEADERS,
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == agent["name"]


def test_update_agent_duplicate_name(api_client: TestClient) -> None:
    _create_agent(api_client, "agent-a")
    agent_b = _create_agent(api_client, "agent-b")

    resp = api_client.patch(
        f"{AGENTS_URL}/{agent_b['id']}",
        json={"name": "agent-a"},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


def test_update_agent_invalid_tool_ids(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"toolIds": ["nonexistent"]},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_update_agent_not_found(api_client: TestClient) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/nonexistent-id",
        json={"name": "x"},
        headers=TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_agent(api_client: TestClient, agent: dict) -> None:
    resp = api_client.delete(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify gone
    resp = api_client.get(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_delete_agent_not_found(api_client: TestClient) -> None:
    resp = api_client.delete(f"{AGENTS_URL}/nonexistent-id", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation_get(api_client: TestClient, agent: dict) -> None:
    """Agent created by tenant_1 is invisible to tenant_2."""
    resp = api_client.get(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_tenant_isolation_list(api_client: TestClient, agent: dict) -> None:
    """Tenant_2 list does not include tenant_1's agents."""
    assert agent["id"]
    resp = api_client.get(AGENTS_URL, headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["items"] == []


def test_tenant_isolation_update(api_client: TestClient, agent: dict) -> None:
    resp = api_client.patch(
        f"{AGENTS_URL}/{agent['id']}",
        json={"name": "hacked"},
        headers=TENANT_2_HEADERS,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_tenant_isolation_delete(api_client: TestClient, agent: dict) -> None:
    resp = api_client.delete(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_2_HEADERS)
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Verify still exists for the owning tenant
    resp = api_client.get(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_1_HEADERS)
    assert resp.status_code == status.HTTP_200_OK


def test_tenant_isolation_duplicate_name_allowed(api_client: TestClient) -> None:
    """Different tenants can use the same agent name."""
    resp1 = api_client.post(
        AGENTS_URL,
        json={"name": "shared-name", "role": "assistant"},
        headers=TENANT_1_HEADERS,
    )
    resp2 = api_client.post(
        AGENTS_URL,
        json={"name": "shared-name", "role": "assistant"},
        headers=TENANT_2_HEADERS,
    )
    assert resp1.status_code == status.HTTP_201_CREATED
    assert resp2.status_code == status.HTTP_201_CREATED
