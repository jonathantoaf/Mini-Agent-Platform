from humps import camelize
from pydantic import BaseModel, ConfigDict


class SharedBaseModel(BaseModel):
    """Base model for all data models with camelCase serialization."""

    model_config = ConfigDict(
        alias_generator=camelize,
        populate_by_name=True,
    )
