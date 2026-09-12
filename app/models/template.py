from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BrewTemplate(Base):
    __tablename__ = "brew_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    roaster: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("beans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bean_origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_process: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The rest of Onyx's attribute wheel — everything the product page states about
    # the coffee itself, as opposed to how it is brewed.
    bean_variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drying_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    harvest_season: Mapped[str | None] = mapped_column(String(100), nullable=True)
    production_roaster: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_extraction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    caffeine_mg: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coffee_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    roast_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    roast_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    flavor_notes_expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Roaster's product page for this coffee (e.g. the Onyx product URL)
    product_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bean_amount_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    grind_setting: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grinder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bloom: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bloom_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bloom_water_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    bloom_pour_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Per-pour schedule (cumulative scale readings and elapsed time per pour)
    first_pour_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_pour_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    second_pour_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    second_pour_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_pour_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_pour_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pour_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grind_suggestion_um: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_amount_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_temp_f: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    brew_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brew_device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    brew_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_filter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    altitude_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    brews: Mapped[list["Brew"]] = relationship("Brew", back_populates="template")
