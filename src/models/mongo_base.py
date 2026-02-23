from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntryBaseModel(BaseModel):
    """Base model for all MongoDB-backed entities."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="", exclude=True, alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: ObjectId | str) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        return v
