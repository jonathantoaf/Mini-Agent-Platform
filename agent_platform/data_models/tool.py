from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel


class ToolCreate(SharedBaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique tool name")
    description: str | None = Field(None, max_length=2000, description="Optional tool description")


class ToolUpdate(SharedBaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, description="New tool name")
    description: str | None = Field(None, max_length=2000, description="New tool description")


class ToolResponse(SharedBaseModel):
    id: str = Field(description="Unique tool identifier")
    name: str = Field(description="Tool name")
    description: str | None = Field(description="Tool description")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
