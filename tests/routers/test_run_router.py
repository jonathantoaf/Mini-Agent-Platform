"""Unit tests for the Run Agent router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from agent_platform.api.dependencies import get_run_service
from agent_platform.api.routers.run_router import router
from agent_platform.data_models.run import RunResponse, ToolCallRecord
from agent_platform.exceptions import (
    AgentNotFoundError,
    InvalidModelError,
    MaxIterationsError,
    PromptInjectionError,
    ToolNotAssignedError,
)
from tests.routers.conftest import TENANT_ID, make_test_client

_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _make_run_response(**overrides: object) -> RunResponse:
    defaults = {
        "execution_id": "exec-1",
        "agent_id": "agent-1",
        "task": "Hello",
        "model": "gpt-4o",
        "final_response": "Done.",
        "tool_calls": [],
        "messages": [],
        "created_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return RunResponse(**defaults)


@pytest.fixture()
def client(mock_service: AsyncMock) -> TestClient:
    return make_test_client(router, (get_run_service, mock_service))


class TestRunAgentEndpoint:
    def test_success_no_tools(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.run_agent.return_value = _make_run_response()

        resp = client.post(
            "/api/v1/agents/agent-1/run",
            json={"task": "Hello", "model": "gpt-4o"},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["executionId"] == "exec-1"
        assert data["finalResponse"] == "Done."
        assert data["toolCalls"] == []

    def test_success_with_tool_calls(self, client: TestClient, mock_service: AsyncMock) -> None:
        mock_service.run_agent.return_value = _make_run_response(
            tool_calls=[
                ToolCallRecord(
                    tool_call_id="call_1",
                    tool_name="web-search",
                    arguments='{"input": "news"}',
                    result="Mock results",
                )
            ],
            final_response="Results found.",
        )

        resp = client.post(
            "/api/v1/agents/agent-1/run",
            json={"task": "search", "model": "gpt-4o"},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["toolCalls"]) == 1
        assert resp.json()["toolCalls"][0]["toolName"] == "web-search"


class TestRunAgentErrorMapping:
    @pytest.mark.parametrize(
        ("exception", "expected_status", "expected_detail"),
        [
            (AgentNotFoundError, status.HTTP_404_NOT_FOUND, "Agent not found."),
            (PromptInjectionError, status.HTTP_400_BAD_REQUEST, "Prompt injection detected."),
            (
                InvalidModelError,
                status.HTTP_400_BAD_REQUEST,
                "Invalid model. Check allowed models.",
            ),
            (
                ToolNotAssignedError,
                status.HTTP_400_BAD_REQUEST,
                "Tool not assigned to this agent.",
            ),
            (
                MaxIterationsError,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Execution exceeded maximum iterations.",
            ),
        ],
        ids=[
            "agent-not-found",
            "prompt-injection",
            "invalid-model",
            "tool-not-assigned",
            "max-iterations",
        ],
    )
    def test_exception_to_http_status(
        self,
        client: TestClient,
        mock_service: AsyncMock,
        exception: type[Exception],
        expected_status: int,
        expected_detail: str,
    ) -> None:
        mock_service.run_agent.side_effect = exception

        resp = client.post(
            "/api/v1/agents/agent-1/run",
            json={"task": "Hello", "model": "gpt-4o"},
        )

        assert resp.status_code == expected_status
        assert resp.json()["detail"] == expected_detail


class TestRunAgentServiceCall:
    def test_passes_correct_args_to_service(
        self, client: TestClient, mock_service: AsyncMock
    ) -> None:
        mock_service.run_agent.return_value = _make_run_response()

        client.post(
            "/api/v1/agents/my-agent-id/run",
            json={"task": "Do something", "model": "gpt-4o-mini"},
        )

        mock_service.run_agent.assert_awaited_once()
        call_args = mock_service.run_agent.call_args
        assert call_args[0][0] == TENANT_ID
        assert call_args[0][1] == "my-agent-id"
        assert call_args[0][2].task == "Do something"
        assert call_args[0][2].model == "gpt-4o-mini"
