from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel

MessageRole = Literal["system", "user", "assistant", "tool"]


class FunctionCall(SharedBaseModel):
    name: str = Field(description="Function name")
    arguments: str = Field(description="JSON-encoded arguments")


class ToolCallData(SharedBaseModel):
    id: str = Field(description="Tool call identifier")
    type: str = Field(default="function", description="Tool call type")
    function: FunctionCall = Field(description="Function call details")


class ChatMessage(SharedBaseModel):
    role: MessageRole = Field(description="Message role")
    content: str | None = Field(None, description="Message text content")
    tool_calls: list[ToolCallData] | None = Field(None, description="Tool calls requested")
    tool_call_id: str | None = Field(
        None, description="ID of the tool call this message responds to"
    )


class FunctionInfo(SharedBaseModel):
    name: str = Field(description="Function name")
    description: str | None = Field(None, description="Function description")
    parameters: dict = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema for parameters",
    )


class ToolDefinition(SharedBaseModel):
    type: str = Field(default="function", description="Tool type")
    function: FunctionInfo = Field(description="Function definition")


class RunRequest(SharedBaseModel):
    task: str = Field(..., min_length=1, max_length=5000, description="Task to execute")
    model: str = Field(..., min_length=1, max_length=100, description="LLM model to use")


class ToolCallRecord(SharedBaseModel):
    tool_call_id: str = Field(description="Tool call identifier")
    tool_name: str = Field(description="Name of the tool called")
    arguments: str = Field(description="JSON-encoded arguments")
    result: str = Field(description="Tool execution result")


class RunResponse(SharedBaseModel):
    execution_id: str = Field(description="Unique execution identifier")
    agent_id: str = Field(description="Agent that was executed")
    task: str = Field(description="Task that was given")
    model: str = Field(description="Model used")
    final_response: str = Field(description="Final agent response")
    tool_calls: list[ToolCallRecord] = Field(description="Tool calls made during execution")
    messages: list[ChatMessage] = Field(description="Full conversation history")
    created_at: datetime = Field(description="Execution timestamp")
