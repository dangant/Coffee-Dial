from datetime import date, datetime

from pydantic import BaseModel, Field


class TemplateBase(BaseModel):
    name: str = Field(max_length=200)
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


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: str | None = None
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


class TemplateRead(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
