from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Brew(Base):
    __tablename__ = "brews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brew_date: Mapped[date] = mapped_column(Date, nullable=False)
    roaster: Mapped[str] = mapped_column(String(200), nullable=False)
    bean_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bean_origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_process: Mapped[str | None] = mapped_column(String(100), nullable=True)
    roast_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    roast_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    flavor_notes_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    bean_amount_grams: Mapped[float] = mapped_column(Float, nullable=False)
    grind_setting: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grinder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bloom: Mapped[bool] = mapped_column(Boolean, default=False)
    bloom_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloom_water_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_amount_ml: Mapped[float] = mapped_column(Float, nullable=False)
    water_temp_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    brew_method: Mapped[str] = mapped_column(String(100), nullable=False)
    brew_device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brew_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_filter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    altitude_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("brew_templates.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    rating: Mapped["Rating | None"] = relationship(
        "Rating", back_populates="brew", uselist=False, cascade="all, delete-orphan"
    )
    template: Mapped["BrewTemplate | None"] = relationship(
        "BrewTemplate", back_populates="brews"
    )
