from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel

MessageRole = Literal["system", "user", "assistant", "tool"]


class FunctionCall(SharedBaseModel):
    name: str
    arguments: str  # JSON string, matching OpenAI format


class ToolCallData(SharedBaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(SharedBaseModel):
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCallData] | None = None
    tool_call_id: str | None = None


class FunctionInfo(SharedBaseModel):
    name: str
    description: str | None = None
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})


class ToolDefinition(SharedBaseModel):
    type: str = "function"
    function: FunctionInfo


class RunRequest(SharedBaseModel):
    task: str = Field(..., min_length=1, max_length=5000)
    model: str = Field(..., min_length=1, max_length=100)


class ToolCallRecord(SharedBaseModel):
    tool_call_id: str
    tool_name: str
    arguments: str
    result: str


class RunResponse(SharedBaseModel):
    execution_id: str
    agent_id: str
    task: str
    model: str
    final_response: str
    tool_calls: list[ToolCallRecord]
    messages: list[ChatMessage]
    created_at: datetime
