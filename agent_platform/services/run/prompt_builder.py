import logging

from agent_platform.data_models.run import ChatMessage, FunctionInfo, ToolDefinition
from agent_platform.db.models.agent import Agent


class PromptBuilder:
    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def build_messages(self, agent: Agent, task: str) -> list[ChatMessage]:
        """Build the initial messages array (system + user) from agent metadata."""
        system_content = self._build_system_prompt(agent)
        return [
            ChatMessage(role="system", content=system_content),
            ChatMessage(role="user", content=task),
        ]

    def build_tools(self, agent: Agent) -> list[ToolDefinition]:
        """Build OpenAI-style tools array from agent's assigned tools."""
        return [
            ToolDefinition(
                function=FunctionInfo(
                    name=tool.name,
                    description=tool.description,
                )
            )
            for tool in agent.tools
        ]

    def _build_system_prompt(self, agent: Agent) -> str:
        lines = [f"You are {agent.name}, a {agent.role}."]
        if agent.description:
            lines.append(agent.description)
        if agent.tools:
            lines.append("\nYou have access to the following tools:")
            for tool in agent.tools:
                desc = f" - {tool.description}" if tool.description else ""
                lines.append(f"- {tool.name}{desc}")
            lines.append("\nUse tools when they are relevant to the user's request.")
        return "\n".join(lines)
