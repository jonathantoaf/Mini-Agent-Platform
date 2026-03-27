"""Integration tests for PostgreSQL Row-Level Security policies.

These tests verify that tenant isolation is enforced at the database level,
not just at the application layer.
"""

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from agent_platform.settings import get_settings

TENANT_1_HEADERS = {"X-API-Key": "sk-tenant1-secret"}
TENANT_2_HEADERS = {"X-API-Key": "sk-tenant2-secret"}
TOOLS_URL = "/api/v1/tools"
AGENTS_URL = "/api/v1/agents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_tool(client: TestClient, name: str, headers: dict | None = None) -> dict:
    resp = client.post(
        TOOLS_URL,
        json={"name": name, "description": "rls test tool"},
        headers=headers or TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _create_agent(client: TestClient, name: str, headers: dict | None = None) -> dict:
    resp = client.post(
        AGENTS_URL,
        json={"name": name, "role": "tester"},
        headers=headers or TENANT_1_HEADERS,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _delete_all(client: TestClient, url: str, headers: dict) -> None:
    resp = client.get(url, params={"limit": 100}, headers=headers)
    if resp.status_code == status.HTTP_200_OK:
        for item in resp.json()["items"]:
            client.delete(f"{url}/{item['id']}", headers=headers)


@pytest.fixture(autouse=True)
def _cleanup(api_client: TestClient):
    yield
    for url in (AGENTS_URL, TOOLS_URL):
        _delete_all(api_client, url, TENANT_1_HEADERS)
        _delete_all(api_client, url, TENANT_2_HEADERS)


# ---------------------------------------------------------------------------
# API-level RLS tests
# ---------------------------------------------------------------------------


class TestRlsApiLevel:
    """Verify tenant isolation via the API (RLS as safety net behind app layer)."""

    def test_tenant_cannot_read_other_tenants_tool(self, api_client: TestClient) -> None:
        tool = _create_tool(api_client, "rls-tool-1", TENANT_1_HEADERS)
        resp = api_client.get(f"{TOOLS_URL}/{tool['id']}", headers=TENANT_2_HEADERS)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_tenant_cannot_list_other_tenants_tools(self, api_client: TestClient) -> None:
        _create_tool(api_client, "rls-tool-2", TENANT_1_HEADERS)
        resp = api_client.get(TOOLS_URL, headers=TENANT_2_HEADERS)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["items"]) == 0

    def test_tenant_cannot_read_other_tenants_agent(self, api_client: TestClient) -> None:
        agent = _create_agent(api_client, "rls-agent-1", TENANT_1_HEADERS)
        resp = api_client.get(f"{AGENTS_URL}/{agent['id']}", headers=TENANT_2_HEADERS)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_tenant_cannot_list_other_tenants_agents(self, api_client: TestClient) -> None:
        _create_agent(api_client, "rls-agent-2", TENANT_1_HEADERS)
        resp = api_client.get(AGENTS_URL, headers=TENANT_2_HEADERS)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()["items"]) == 0

    def test_tenant_can_read_own_data(self, api_client: TestClient) -> None:
        tool = _create_tool(api_client, "rls-own-tool", TENANT_1_HEADERS)
        resp = api_client.get(f"{TOOLS_URL}/{tool['id']}", headers=TENANT_1_HEADERS)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == tool["id"]


# ---------------------------------------------------------------------------
# DB-level RLS tests (bypass application layer)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_engine():
    """Create a raw async engine for direct DB access outside the app's DI."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()


class TestRlsDbLevel:
    """Verify RLS enforcement directly at the database level."""

    @pytest.mark.asyncio
    async def test_no_rows_visible_without_session_variable(self, db_engine) -> None:
        """Without app.current_tenant_id set, queries should return no rows."""
        async with AsyncSession(db_engine) as session:
            result = await session.execute(text("SELECT count(*) FROM tools"))
            count = result.scalar()
            assert count == 0

    @pytest.mark.asyncio
    async def test_cross_tenant_query_blocked(self, db_engine) -> None:
        """Insert as tenant_1, query as tenant_2 — should see no rows."""
        # Insert as tenant_1
        async with AsyncSession(db_engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', 'tenant_1', true)")
            )
            await session.execute(
                text(
                    "INSERT INTO tools (id, tenant_id, name) "
                    "VALUES ('rls-test-id-1', 'tenant_1', 'rls-db-tool')"
                )
            )
            await session.commit()

        # Query as tenant_2 — should see nothing
        async with AsyncSession(db_engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', 'tenant_2', true)")
            )
            result = await session.execute(text("SELECT id FROM tools WHERE id = 'rls-test-id-1'"))
            assert result.fetchone() is None

        # Verify tenant_1 can see its own row
        async with AsyncSession(db_engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', 'tenant_1', true)")
            )
            result = await session.execute(text("SELECT id FROM tools WHERE id = 'rls-test-id-1'"))
            row = result.fetchone()
            assert row is not None
            assert row[0] == "rls-test-id-1"

            # Cleanup
            await session.execute(text("DELETE FROM tools WHERE id = 'rls-test-id-1'"))
            await session.commit()

    @pytest.mark.asyncio
    async def test_insert_with_mismatched_tenant_id_blocked(self, db_engine) -> None:
        """WITH CHECK policy should block inserts where tenant_id doesn't match session var."""
        async with AsyncSession(db_engine) as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant_id', 'tenant_1', true)")
            )
            with pytest.raises(ProgrammingError, match="row-level security"):
                await session.execute(
                    text(
                        "INSERT INTO tools (id, tenant_id, name) "
                        "VALUES ('rls-test-id-2', 'tenant_2', 'rls-mismatch-tool')"
                    )
                )
            await session.rollback()
