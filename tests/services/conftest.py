"""Shared test builders for service tests."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from agent_platform.db.models.tool import Tool


def make_tool(
    tool_id: str = "t1",
    tenant_id: str = "tenant_1",
    name: str = "web-search",
    description: str | None = "Search the web",
) -> MagicMock:
    tool = MagicMock(spec=Tool)
    tool.id = tool_id
    tool.tenant_id = tenant_id
    tool.name = name
    tool.description = description
    tool.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    tool.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return tool
