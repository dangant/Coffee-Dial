from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Top to bottom, matching the tiermaker board this was modelled on.
TIERS = ["S", "A", "B", "C", "D", "E", "F"]
# S is best, so a higher score means a better coffee and averages sort the useful way.
TIER_SCORES = {tier: len(TIERS) - i for i, tier in enumerate(TIERS)}


class TierEntry(Base):
    """One coffee's place on the tier board.

    The unit is a coffee, not a recipe: an Onyx import writes both an espresso and a
    pour-over template for the same bean, and ranking those separately would put the
    coffee on the board twice and double its weight in the analytics. ``coffee_key``
    (the normalized bean name) is unique for that reason.

    Identity is denormalized so a coffee typed in by hand — one brewed before this app
    existed — behaves exactly like one that came from a template. When ``template_id``
    is set the live template still wins, so editing a template updates the board.
    """

    __tablename__ = "tier_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coffee_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    bean_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roaster: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bean_process: Mapped[str | None] = mapped_column(String(100), nullable=True)
    flavor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("brew_templates.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # Null means unranked — the coffee sits in the tray rather than on the board.
    tier: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
