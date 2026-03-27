import pytest

from agent_platform.services.run.prompt_builder import PromptBuilder
from tests.services.run.conftest import make_agent, make_tool


@pytest.fixture()
def builder() -> PromptBuilder:
    return PromptBuilder()


class TestBuildMessages:
    def test_basic_messages(self, builder: PromptBuilder) -> None:
        agent = make_agent()
        messages = builder.build_messages(agent, "Do something")

        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert messages[1].content == "Do something"

    def test_system_prompt_contains_agent_info(self, builder: PromptBuilder) -> None:
        agent = make_agent(name="Analyzer", role="data analyst", description="Analyzes data")
        messages = builder.build_messages(agent, "Analyze this")

        system = messages[0].content
        assert "Analyzer" in system
        assert "data analyst" in system
        assert "Analyzes data" in system

    def test_system_prompt_with_tools(self, builder: PromptBuilder) -> None:
        tools = [
            make_tool("web-search", "Search the web"),
            make_tool("calculator", "Perform calculations"),
        ]
        agent = make_agent(tools=tools)
        messages = builder.build_messages(agent, "Search for news")

        system = messages[0].content
        assert "web-search" in system
        assert "Search the web" in system
        assert "calculator" in system

    def test_system_prompt_without_description(self, builder: PromptBuilder) -> None:
        agent = make_agent(description=None)
        messages = builder.build_messages(agent, "Hello")

        system = messages[0].content
        assert "TestAgent" in system
        assert "assistant" in system

    def test_system_prompt_without_tools(self, builder: PromptBuilder) -> None:
        agent = make_agent(tools=[])
        messages = builder.build_messages(agent, "Hello")

        system = messages[0].content
        assert "tools" not in system.lower() or "You have access" not in system


class TestBuildTools:
    def test_builds_tool_definitions(self, builder: PromptBuilder) -> None:
        tools = [
            make_tool("web-search", "Search the web"),
            make_tool("calculator", None),
        ]
        agent = make_agent(tools=tools)
        result = builder.build_tools(agent)

        assert len(result) == 2
        assert result[0].type == "function"
        assert result[0].function.name == "web-search"
        assert result[0].function.description == "Search the web"
        assert result[1].function.name == "calculator"
        assert result[1].function.description is None

    def test_empty_tools(self, builder: PromptBuilder) -> None:
        agent = make_agent(tools=[])
        result = builder.build_tools(agent)
        assert result == []
