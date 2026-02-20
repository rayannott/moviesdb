from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


class EntryBaseModel(BaseModel):
    id: str = Field(default="", exclude=True, alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        return v
