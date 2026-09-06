"""Reconcile roaster names that drifted apart.

The same roaster gets typed differently over time — "Onyx" on one template, "Onyx Coffee
Lab" on another — and every grouping then splits it in two, so the tier and analytics
charts report one roaster as two weaker ones. Merging rewrites the name across every
table that records it, rather than mapping at read time, so all four surfaces (tiers,
analytics, shelf, brews) agree without each having to know about aliases.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.inventory import BeanInventory
from app.models.template import BrewTemplate
from app.models.tier_entry import TierEntry

# Every table that stores a roaster name as free text.
ROASTER_TABLES = (Brew, BrewTemplate, TierEntry)


def list_roasters(db: Session) -> list[dict]:
    """Every roaster name in use, with where it appears — enough to spot duplicates."""
    counts: dict[str, dict] = {}
    for model, field in (
        (Brew, "brews"), (BrewTemplate, "templates"),
        (TierEntry, "tier_entries"), (BeanInventory, "shelf"),
    ):
        rows = (
            db.query(model.roaster, func.count(model.id))
            .filter(model.roaster.isnot(None), model.roaster != "")
            .group_by(model.roaster)
            .all()
        )
        for name, count in rows:
            entry = counts.setdefault(
                name, {"roaster": name, "brews": 0, "templates": 0,
                       "tier_entries": 0, "shelf": 0, "total": 0}
            )
            entry[field] += count
            entry["total"] += count
    return sorted(counts.values(), key=lambda r: (-r["total"], r["roaster"].lower()))


def _merge_inventory(db: Session, source: str, target: str) -> int:
    """Move shelf rows, folding any that would collide on (bean_name, roaster).

    bean_inventory is unique on that pair, so a bean stocked under both spellings
    can't simply be renamed — the two bags are the same bean and are combined.
    """
    moved = 0
    for row in db.query(BeanInventory).filter(BeanInventory.roaster == source).all():
        existing = (
            db.query(BeanInventory)
            .filter(
                BeanInventory.bean_name == row.bean_name,
                BeanInventory.roaster == target,
                BeanInventory.id != row.id,
            )
            .first()
        )
        if existing:
            existing.initial_amount_grams += row.initial_amount_grams
            if row.price is not None:
                existing.price = (existing.price or 0) + row.price
            existing.used_offset_grams = (existing.used_offset_grams or 0) + (
                row.used_offset_grams or 0
            )
            db.delete(row)
        else:
            row.roaster = target
        moved += 1
    return moved


def merge_roasters(db: Session, source: str, target: str) -> dict:
    """Rename every occurrence of ``source`` to ``target``. Returns rows touched."""
    source, target = (source or "").strip(), (target or "").strip()
    if not source or not target:
        raise ValueError("Both roaster names are required.")
    if source == target:
        raise ValueError("Those are already the same roaster.")

    counts = {}
    for model in ROASTER_TABLES:
        counts[model.__tablename__] = (
            db.query(model)
            .filter(model.roaster == source)
            .update({model.roaster: target}, synchronize_session=False)
        )
    counts["bean_inventory"] = _merge_inventory(db, source, target)
    db.commit()

    return {"source": source, "target": target, "updated": counts,
            "total": sum(counts.values())}
