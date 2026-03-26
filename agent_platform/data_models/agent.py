from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel
from agent_platform.data_models.tool import ToolResponse


class AgentCreate(SharedBaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    tool_ids: list[str] = Field(default_factory=list)


class AgentUpdate(SharedBaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    role: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    tool_ids: list[str] | None = Field(None)


class AgentResponse(SharedBaseModel):
    id: str
    name: str
    role: str
    description: str | None
    tools: list[ToolResponse]
    created_at: datetime
    updated_at: datetime
