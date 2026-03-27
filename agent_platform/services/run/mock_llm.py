import hashlib
import json
import logging
import re

from agent_platform.data_models.run import (
    ChatMessage,
    FunctionCall,
    ToolCallData,
    ToolDefinition,
)


class MockLlmAdapter:
    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def complete(self, messages: list[ChatMessage], tools: list[ToolDefinition]) -> ChatMessage:
        """Return a deterministic assistant response based on keyword matching."""
        if not tools:
            return self._final_response(messages)

        user_task = self._extract_user_task(messages)
        called_tools = self._extract_called_tool_names(messages)
        iteration = len(called_tools)

        for tool_def in tools:
            tool_name = tool_def.function.name
            if tool_name in called_tools:
                continue
            if self._matches_task(tool_name, user_task):
                self._logger.debug(
                    f"Mock LLM requesting tool call tool={tool_name} iteration={iteration}"
                )
                return self._tool_call_response(tool_name, user_task, iteration)

        return self._final_response(messages)

    def _matches_task(self, tool_name: str, task: str) -> bool:
        """Check if any keyword from the tool name appears in the task."""
        keywords = re.split(r"[-_]", tool_name)
        task_lower = task.lower()
        return any(kw.lower() in task_lower for kw in keywords if len(kw) > 1)

    def _extract_user_task(self, messages: list[ChatMessage]) -> str:
        """Extract the original user task from the messages."""
        for msg in messages:
            if msg.role == "user":
                return msg.content or ""
        return ""

    def _extract_called_tool_names(self, messages: list[ChatMessage]) -> set[str]:
        """Find tool names that have already been called by scanning tool result messages."""
        called: set[str] = set()
        tool_call_id_to_name: dict[str, str] = {}

        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_id_to_name[tc.id] = tc.function.name
            if msg.role == "tool" and msg.tool_call_id:
                name = tool_call_id_to_name.get(msg.tool_call_id)
                if name:
                    called.add(name)

        return called

    def _tool_call_response(self, tool_name: str, user_task: str, iteration: int) -> ChatMessage:
        call_id = self._generate_call_id(tool_name, iteration)
        arguments = json.dumps({"input": user_task})
        return ChatMessage(
            role="assistant",
            tool_calls=[
                ToolCallData(
                    id=call_id,
                    function=FunctionCall(name=tool_name, arguments=arguments),
                )
            ],
        )

    def _final_response(self, messages: list[ChatMessage]) -> ChatMessage:
        """Generate a deterministic final response summarizing the conversation."""
        tool_results = [msg for msg in messages if msg.role == "tool"]
        if tool_results:
            parts = ["Based on the tool results:"]
            for result in tool_results:
                parts.append(f"- {result.content}")
            parts.append("Task completed successfully.")
            content = "\n".join(parts)
        else:
            user_task = self._extract_user_task(messages)
            content = f"I'll help you with: {user_task}. Task completed successfully."
        return ChatMessage(role="assistant", content=content)

    @staticmethod
    def _generate_call_id(tool_name: str, iteration: int) -> str:
        raw = f"{tool_name}:{iteration}"
        # MD5 used for deterministic ID generation, not security
        return "call_" + hashlib.md5(raw.encode()).hexdigest()[:12]  # noqa: S324
