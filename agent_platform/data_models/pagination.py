"""Pagination data models for cursor-based pagination."""

import base64
import json
from datetime import datetime

from pydantic import Field

from agent_platform.data_models.base import SharedBaseModel


class CursorData(SharedBaseModel):
    """Internal cursor data structure."""

    created_at: datetime
    id: str


def encode_cursor(created_at: datetime, item_id: str) -> str:
    """Encode pagination cursor from created_at and id.

    Args:
        created_at: Timestamp of the last item.
        item_id: ID of the last item.

    Returns:
        Base64 encoded cursor string.
    """
    data = {"created_at": created_at.isoformat(), "id": item_id}
    json_bytes = json.dumps(data).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("utf-8")


def decode_cursor(cursor: str) -> CursorData | None:
    """Decode pagination cursor to created_at and id.

    Args:
        cursor: Base64 encoded cursor string.

    Returns:
        CursorData if valid, None otherwise.
    """
    try:
        json_bytes = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        data = json.loads(json_bytes.decode("utf-8"))
        return CursorData(
            created_at=datetime.fromisoformat(data["created_at"]),
            id=data["id"],
        )
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


class PaginatedResponse[T](SharedBaseModel):
    """Generic paginated response wrapper."""

    items: list[T]
    next_cursor: str | None = Field(None, description="Cursor for the next page")
    has_more: bool = Field(False, description="Whether there are more items")


class PaginationParams(SharedBaseModel):
    """Pagination query parameters."""

    cursor: str | None = Field(None, description="Pagination cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Number of items per page")
