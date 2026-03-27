import pytest

from agent_platform.data_models.run import (
    ChatMessage,
    FunctionCall,
    FunctionInfo,
    ToolCallData,
    ToolDefinition,
)
from agent_platform.services.run.mock_llm import MockLlmAdapter


@pytest.fixture()
def llm() -> MockLlmAdapter:
    return MockLlmAdapter()


def _tool_def(name: str, description: str = "") -> ToolDefinition:
    return ToolDefinition(function=FunctionInfo(name=name, description=description))


def _base_messages(task: str) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are a test agent."),
        ChatMessage(role="user", content=task),
    ]


class TestMockLlmComplete:
    def test_no_tools_returns_final_response(self, llm: MockLlmAdapter) -> None:
        messages = _base_messages("tell me a joke")
        result = llm.complete(messages, [])

        assert result.role == "assistant"
        assert result.content is not None
        assert result.tool_calls is None

    def test_matching_tool_triggers_call(self, llm: MockLlmAdapter) -> None:
        messages = _base_messages("search for AI news")
        tools = [_tool_def("web-search")]
        result = llm.complete(messages, tools)

        assert result.role == "assistant"
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].function.name == "web-search"

    def test_no_keyword_match_returns_final(self, llm: MockLlmAdapter) -> None:
        messages = _base_messages("tell me a joke")
        tools = [_tool_def("web-search")]
        result = llm.complete(messages, tools)

        assert result.role == "assistant"
        assert result.content is not None
        assert result.tool_calls is None

    def test_already_called_tool_skipped(self, llm: MockLlmAdapter) -> None:
        call_id = "call_test123"
        messages = [
            ChatMessage(role="system", content="You are a test agent."),
            ChatMessage(role="user", content="search for news"),
            ChatMessage(
                role="assistant",
                tool_calls=[
                    ToolCallData(
                        id=call_id,
                        function=FunctionCall(
                            name="web-search", arguments='{"input": "search for news"}'
                        ),
                    )
                ],
            ),
            ChatMessage(role="tool", content="Some results", tool_call_id=call_id),
        ]
        tools = [_tool_def("web-search")]
        result = llm.complete(messages, tools)

        assert result.role == "assistant"
        assert result.content is not None
        assert result.tool_calls is None

    def test_multi_tool_calls_sequentially(self, llm: MockLlmAdapter) -> None:
        """First call matches web-search, second matches data-calculator."""
        messages = _base_messages("search for data and use the calculator")
        tools = [_tool_def("web-search"), _tool_def("data-calculator")]

        # First call — should pick web-search (keyword "search")
        result1 = llm.complete(messages, tools)
        assert result1.tool_calls is not None
        assert result1.tool_calls[0].function.name == "web-search"

        # Simulate the tool call and result
        messages.append(result1)
        messages.append(
            ChatMessage(
                role="tool",
                content="Search results",
                tool_call_id=result1.tool_calls[0].id,
            )
        )

        # Second call — should pick data-calculator (keyword "calculator")
        result2 = llm.complete(messages, tools)
        assert result2.tool_calls is not None
        assert result2.tool_calls[0].function.name == "data-calculator"

    def test_tool_call_id_is_deterministic(self, llm: MockLlmAdapter) -> None:
        messages = _base_messages("search for news")
        tools = [_tool_def("web-search")]

        result1 = llm.complete(messages, tools)
        result2 = llm.complete(messages, tools)

        assert result1.tool_calls[0].id == result2.tool_calls[0].id

    def test_orphaned_tool_result_ignored(self, llm: MockLlmAdapter) -> None:
        """Tool result with unknown tool_call_id should not count as a called tool."""
        messages = [
            ChatMessage(role="system", content="System"),
            ChatMessage(role="user", content="search for news"),
            ChatMessage(role="tool", content="Orphaned result", tool_call_id="unknown_id"),
        ]
        tools = [_tool_def("web-search")]
        result = llm.complete(messages, tools)

        # Should still call web-search since the orphaned result isn't matched
        assert result.tool_calls is not None
        assert result.tool_calls[0].function.name == "web-search"

    def test_no_user_message_returns_final(self, llm: MockLlmAdapter) -> None:
        messages = [ChatMessage(role="system", content="System prompt only")]
        tools = [_tool_def("web-search")]
        result = llm.complete(messages, tools)

        assert result.role == "assistant"
        assert result.content is not None

    def test_final_response_includes_tool_results(self, llm: MockLlmAdapter) -> None:
        call_id = "call_test123"
        messages = [
            ChatMessage(role="system", content="You are a test agent."),
            ChatMessage(role="user", content="do something"),
            ChatMessage(
                role="assistant",
                tool_calls=[
                    ToolCallData(
                        id=call_id,
                        function=FunctionCall(name="some-tool", arguments="{}"),
                    )
                ],
            ),
            ChatMessage(role="tool", content="Tool output here", tool_call_id=call_id),
        ]
        result = llm.complete(messages, [])

        assert result.content is not None
        assert "Tool output here" in result.content
