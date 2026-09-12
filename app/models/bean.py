from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Bean(Base):
    """One coffee, with an id the other tables can point at.

    Brews, templates, the shelf and the tier board used to be joined by the bean
    name alone, so a trailing space or a second spelling filed one coffee as two —
    the George Howell Dota case. The spelling now hangs off this row instead of
    being the identity.

    ``match_key`` is :func:`app.services.naming.bean_key` flattened to a string and
    made unique, so two spellings of the same coffee can't both become beans. The
    name columns on the other tables are kept in step with ``name``/``roaster`` here
    rather than dropped: every existing read path still works, and a row the backfill
    couldn't resolve stays visible instead of vanishing.
    """

    __tablename__ = "beans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    roaster: Mapped[str | None] = mapped_column(String(200), nullable=True)
    match_key: Mapped[str] = mapped_column(
        String(400), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
