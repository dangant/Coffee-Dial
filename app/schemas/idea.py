from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class IdeaBase(BaseModel):
    title: str = Field(max_length=200)
    details: str | None = None


class IdeaCreate(IdeaBase):
    pass


class IdeaUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    details: str | None = None
    is_done: bool | None = None


class IdeaScreenshotRead(BaseModel):
    id: int
    idea_id: int
    filename: str
    content_type: str
    width: int
    height: int
    byte_size: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def url(self) -> str:
        """Where the bytes live, so the page never has to build this path itself."""
        return f"/api/v1/ideas/screenshots/{self.id}"


class IdeaRead(IdeaBase):
    id: int
    is_done: bool
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    screenshots: list[IdeaScreenshotRead] = []

    model_config = {"from_attributes": True}
