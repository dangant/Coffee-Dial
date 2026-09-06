from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdeaScreenshot(Base):
    """An image pinned to an enhancement idea — usually a pasted screenshot.

    The bytes live in the database rather than on disk: the app runs on Railway, whose
    filesystem is replaced on every deploy, so a file written next to the app would not
    survive one. LargeBinary is bytea on Postgres and BLOB on SQLite, so the same column
    works in production and local development.
    """

    __tablename__ = "idea_screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
