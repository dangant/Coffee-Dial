from datetime import date, datetime

from pydantic import BaseModel, Field


class BrewBase(BaseModel):
    brew_date: date
    roaster: str = Field(max_length=200)
    bean_name: str = Field(max_length=200)
    bean_origin: str | None = None
    bean_process: str | None = None
    roast_date: date | None = None
    roast_level: str | None = None
    flavor_notes_expected: str | None = None
    bean_amount_grams: float
    grind_setting: str | None = None
    grinder: str | None = None
    bloom: bool = False
    bloom_time_seconds: int | None = None
    bloom_water_ml: float | None = None
    water_amount_ml: float
    water_temp_f: float | None = None
    water_temp_c: float | None = None
    brew_method: str = Field(max_length=100)
    brew_device: str | None = None
    brew_time_seconds: int | None = None
    water_filter_type: str | None = None
    altitude_ft: int | None = None
    notes: str | None = None
    template_id: int | None = None


class BrewCreate(BrewBase):
    pass


class BrewUpdate(BaseModel):
    brew_date: date | None = None
    roaster: str | None = None
    bean_name: str | None = None
    bean_origin: str | None = None
    bean_process: str | None = None
    roast_date: date | None = None
    roast_level: str | None = None
    flavor_notes_expected: str | None = None
    bean_amount_grams: float | None = None
    grind_setting: str | None = None
    grinder: str | None = None
    bloom: bool | None = None
    bloom_time_seconds: int | None = None
    bloom_water_ml: float | None = None
    water_amount_ml: float | None = None
    water_temp_f: float | None = None
    water_temp_c: float | None = None
    brew_method: str | None = None
    brew_device: str | None = None
    brew_time_seconds: int | None = None
    water_filter_type: str | None = None
    altitude_ft: int | None = None
    notes: str | None = None
    template_id: int | None = None


class RatingInline(BaseModel):
    id: int
    overall_score: float
    bitterness: float | None = None
    acidity: float | None = None
    sweetness: float | None = None
    body: float | None = None
    aroma: float | None = None
    aftertaste: float | None = None
    flavor_notes_experienced: str | None = None
    comments: str | None = None

    model_config = {"from_attributes": True}


class BrewRead(BrewBase):
    id: int
    created_at: datetime
    updated_at: datetime
    rating: RatingInline | None = None

    model_config = {"from_attributes": True}


class BrewListRead(BaseModel):
    id: int
    brew_date: date
    roaster: str
    bean_name: str
    brew_method: str
    overall_score: float | None = None

    model_config = {"from_attributes": True}
