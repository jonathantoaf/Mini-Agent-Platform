from datetime import UTC, datetime

from humps import camelize
from pydantic import BaseModel, ConfigDict


class SharedBaseModel(BaseModel):
    """Base model for all data models with camelCase serialization."""

    model_config = ConfigDict(
        alias_generator=camelize,
        populate_by_name=True,
    )

    def model_dump_json_with_timezone(self) -> str:
        """Serialize to JSON with UTC timezone for datetime fields."""

        def serialize_datetime(dt: datetime) -> str:
            if not dt.tzinfo:
                return dt.replace(tzinfo=UTC).isoformat()
            return dt.isoformat()

        return self.model_dump_json()
