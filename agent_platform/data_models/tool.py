from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel


class ToolCreate(SharedBaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class ToolUpdate(SharedBaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class ToolResponse(SharedBaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
