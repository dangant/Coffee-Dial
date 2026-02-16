from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RecommendationRule(Base):
    __tablename__ = "recommendation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_field: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_operator: Mapped[str] = mapped_column(String(10), nullable=False)  # >=, <=, ==
    condition_value: Mapped[str] = mapped_column(String(50), nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # grind, temp, time, etc.
