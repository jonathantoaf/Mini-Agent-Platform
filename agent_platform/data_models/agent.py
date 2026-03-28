from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel
from agent_platform.data_models.tool import ToolResponse


class AgentCreate(SharedBaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique agent name")
    role: str = Field(..., min_length=1, max_length=255, description="Agent role or persona")
    description: str | None = Field(None, max_length=2000, description="Optional agent description")
    tool_ids: list[str] = Field(default_factory=list, description="Tool IDs to assign")


class AgentUpdate(SharedBaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="New agent name")
    role: str | None = Field(None, min_length=1, max_length=255, description="New agent role")
    description: str | None = Field(None, max_length=2000, description="New agent description")
    tool_ids: list[str] | None = Field(None, description="New tool IDs to assign")


class AgentResponse(SharedBaseModel):
    id: str = Field(description="Unique agent identifier")
    name: str = Field(description="Agent name")
    role: str = Field(description="Agent role")
    description: str | None = Field(description="Agent description")
    tools: list[ToolResponse] = Field(description="Assigned tools")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
