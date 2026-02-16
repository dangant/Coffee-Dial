from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BrewTemplate(Base):
    __tablename__ = "brew_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    roaster: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_process: Mapped[str | None] = mapped_column(String(100), nullable=True)
    roast_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    flavor_notes_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    bean_amount_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    grind_setting: Mapped[float | None] = mapped_column(Float, nullable=True)
    grinder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bloom: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bloom_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloom_water_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_amount_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_temp_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    brew_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brew_device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brew_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_filter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paper_filter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    altitude_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    brews: Mapped[list["Brew"]] = relationship("Brew", back_populates="template")
