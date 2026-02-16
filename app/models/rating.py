from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brew_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("brews.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    bitterness: Mapped[float | None] = mapped_column(Float, nullable=True)
    acidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    sweetness: Mapped[float | None] = mapped_column(Float, nullable=True)
    body: Mapped[float | None] = mapped_column(Float, nullable=True)
    aroma: Mapped[float | None] = mapped_column(Float, nullable=True)
    aftertaste: Mapped[float | None] = mapped_column(Float, nullable=True)
    flavor_notes_experienced: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    brew: Mapped["Brew"] = relationship("Brew", back_populates="rating")
