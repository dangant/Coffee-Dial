from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BeanInventory(Base):
    __tablename__ = "bean_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bean_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roaster: Mapped[str | None] = mapped_column(String(200), nullable=True)
    initial_amount_grams: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (UniqueConstraint("bean_name", "roaster", name="uq_bean_roaster"),)
