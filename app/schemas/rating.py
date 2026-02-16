from pydantic import BaseModel, Field


class RatingBase(BaseModel):
    overall_score: float = Field(ge=1, le=10)
    bitterness: float | None = Field(default=None, ge=1, le=5)
    acidity: float | None = Field(default=None, ge=1, le=5)
    sweetness: float | None = Field(default=None, ge=1, le=5)
    body: float | None = Field(default=None, ge=1, le=5)
    aroma: float | None = Field(default=None, ge=1, le=5)
    aftertaste: float | None = Field(default=None, ge=1, le=5)
    flavor_notes_experienced: str | None = None
    comments: str | None = None


class RatingCreate(RatingBase):
    pass


class RatingUpdate(BaseModel):
    overall_score: float | None = Field(default=None, ge=1, le=10)
    bitterness: float | None = Field(default=None, ge=1, le=5)
    acidity: float | None = Field(default=None, ge=1, le=5)
    sweetness: float | None = Field(default=None, ge=1, le=5)
    body: float | None = Field(default=None, ge=1, le=5)
    aroma: float | None = Field(default=None, ge=1, le=5)
    aftertaste: float | None = Field(default=None, ge=1, le=5)
    flavor_notes_experienced: str | None = None
    comments: str | None = None


class RatingRead(RatingBase):
    id: int
    brew_id: int

    model_config = {"from_attributes": True}
