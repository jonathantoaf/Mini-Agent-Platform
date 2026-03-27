import pytest

from agent_platform.services.run.mock_tool_executor import MockToolExecutor


@pytest.fixture()
def executor() -> MockToolExecutor:
    return MockToolExecutor()


class TestMockToolExecutor:
    def test_returns_deterministic_result(self, executor: MockToolExecutor) -> None:
        result = executor.execute("web-search", '{"query": "AI news"}')
        assert result == 'Mock result for web-search with arguments: {"query": "AI news"}'

    def test_different_tools_different_results(self, executor: MockToolExecutor) -> None:
        result1 = executor.execute("web-search", '{"q": "test"}')
        result2 = executor.execute("calculator", '{"q": "test"}')
        assert result1 != result2
        assert "web-search" in result1
        assert "calculator" in result2

    def test_same_input_same_output(self, executor: MockToolExecutor) -> None:
        result1 = executor.execute("tool-a", '{"x": 1}')
        result2 = executor.execute("tool-a", '{"x": 1}')
        assert result1 == result2
