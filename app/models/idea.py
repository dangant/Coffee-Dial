from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Idea(Base):
    """An enhancement idea for the app itself — jotted down, then ticked off."""

    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Gates what Claude may do with this idea during "Review ideas": true means plan
    # and stop, false is an explicit grant to implement and push without a round trip.
    # Defaults to true — forgetting to tick a box must not ship something unreviewed.
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Stamped when the idea is ticked, cleared if it is reopened.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Deleting an idea takes its screenshots with it rather than orphaning the rows.
    screenshots: Mapped[list["IdeaScreenshot"]] = relationship(  # noqa: F821
        "IdeaScreenshot",
        cascade="all, delete-orphan",
        order_by="IdeaScreenshot.created_at",
        lazy="selectin",
    )
