from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel
from agent_platform.data_models.run import ChatMessage, ToolCallRecord


class ExecutionResponse(SharedBaseModel):
    execution_id: str = Field(description="Unique execution identifier")
    agent_id: str = Field(description="Agent that was executed")
    task: str = Field(description="Task that was given to the agent")
    model: str = Field(description="Model used for the execution")
    final_response: str = Field(description="Final response from the agent")
    tool_calls: list[ToolCallRecord] = Field(description="Tool calls made during execution")
    messages: list[ChatMessage] = Field(description="Full conversation message history")
    created_at: datetime = Field(description="When the execution was created")
