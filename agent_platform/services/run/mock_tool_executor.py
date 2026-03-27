import logging


class MockToolExecutor:
    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def execute(self, tool_name: str, arguments: str) -> str:
        """Execute a mock tool call and return a deterministic result."""
        self._logger.debug(f"Executing mock tool tool={tool_name}")
        return f"Mock result for {tool_name} with arguments: {arguments}"
