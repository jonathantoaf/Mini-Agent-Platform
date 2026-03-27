from unittest.mock import MagicMock


def make_tool(name: str, description: str | None = None) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def make_agent(
    agent_id: str = "agent-1",
    name: str = "TestAgent",
    role: str = "assistant",
    description: str | None = "A test agent",
    tools: list | None = None,
) -> MagicMock:
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.role = role
    agent.description = description
    agent.tools = tools or []
    return agent
