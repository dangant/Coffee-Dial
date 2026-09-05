from datetime import datetime

from pydantic import BaseModel, Field


class IdeaBase(BaseModel):
    title: str = Field(max_length=200)
    details: str | None = None


class IdeaCreate(IdeaBase):
    pass


class IdeaUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    details: str | None = None
    is_done: bool | None = None


class IdeaRead(IdeaBase):
    id: int
    is_done: bool
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
